// UI audit: opens the sample programme in a real browser and walks every view, in both
// themes, at desktop and phone width, with each floating panel opened. In each state it
// checks the layout faults a unit test cannot see, and runs axe (WCAG 2 A/AA). It fails
// on any finding.
//
//   node scripts/ui-audit.mjs [url] [--shots dir]
//
// The url is a running server build (default http://localhost:8000). CHROME_PATH picks
// a Chromium other than Playwright's own.
//
// Layout faults it checks:
//   - a floating panel with no background, or with content spilling out of or wider
//     than its box (a panel given top and bottom at once collapses to a sliver);
//   - a floating panel partly off-screen;
//   - text spilling out of its box;
//   - the page scrolling sideways.

import { chromium } from 'playwright'
import { readFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const args = process.argv.slice(2)
const shotsAt = args.indexOf('--shots')
const SHOTS = shotsAt >= 0 ? args.splice(shotsAt, 2)[1] : null
const BASE = args[0] || 'http://localhost:8000/'
const SAMPLE = fileURLToPath(new URL('../../examples/sample-schedule.xer', import.meta.url))
const AXE = readFileSync(createRequire(import.meta.url).resolve('axe-core/axe.min.js'), 'utf8')
if (SHOTS) mkdirSync(SHOTS, { recursive: true })

// An "earlier" file for Compare: the sample with every original duration a fifth longer
// and two links fewer, so the comparison has changes to show.
function earlierFile() {
  let table = '', fields = [], dropped = 0
  const lines = readFileSync(SAMPLE, 'utf8').split('\n').flatMap(l => {
    if (l.startsWith('%T')) table = l.split('\t')[1]
    if (l.startsWith('%F')) fields = l.split('\t').slice(1)
    if (!l.startsWith('%R')) return [l]
    if (table === 'TASKPRED' && dropped < 2) { dropped++; return [] }
    if (table !== 'TASK') return [l]
    const r = l.split('\t'), i = fields.indexOf('target_drtn_hr_cnt') + 1
    if (r[i] && !isNaN(+r[i])) r[i] = String(+r[i] * 1.2)
    return [r.join('\t')]
  })
  return { name: 'sample-earlier.xer', mimeType: 'application/octet-stream', buffer: Buffer.from(lines.join('\n')) }
}

// Runs in the page.
function layoutFaults() {
  const found = []
  const shown = e => {
    const r = e.getBoundingClientRect(), c = getComputedStyle(e)
    return r.width > 0 && r.height > 0 && c.visibility !== 'hidden' && c.display !== 'none' && +c.opacity > 0.05
  }
  const name = e => `${e.tagName.toLowerCase()}.${String(e.className).trim().split(/\s+/).join('.')} "${(e.textContent || '').trim().slice(0, 30)}"`
  for (const e of document.querySelectorAll('body *')) {
    if (!shown(e) || e.closest('svg')) continue
    const c = getComputedStyle(e)
    if ((c.position === 'absolute' || c.position === 'fixed') && c.zIndex !== 'auto' && +c.zIndex >= 10 && e.children.length) {
      const r = e.getBoundingClientRect()
      const onScreen = r.right > 0 && r.left < innerWidth // a closed drawer sits wholly off-screen
      if ((c.backgroundColor === 'rgba(0, 0, 0, 0)') && c.backgroundImage === 'none' && e.querySelector('button, a, p, li'))
        found.push(['floating panel with no background', name(e)])
      if (e.scrollWidth > e.clientWidth + 2)
        found.push(['floating content wider than its box', `${name(e)} ${e.clientWidth}px < ${e.scrollWidth}px`])
      if (c.overflowY === 'visible' && e.scrollHeight > e.clientHeight + 2)
        found.push(['floating content spills out of its box', `${name(e)} ${e.clientHeight}px < ${e.scrollHeight}px`])
      if (onScreen && (r.left < -1 || r.top < -1 || r.right > innerWidth + 1 || r.bottom > innerHeight + 1))
        found.push(['floating panel off-screen', `${name(e)} [${[r.left, r.top, r.right, r.bottom].map(Math.round)}]`])
    }
    const text = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())
    if (text && c.display !== 'inline' && c.overflowX === 'visible' && c.whiteSpace !== 'normal' && e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 2)
      found.push(['text spills out of its box', `${name(e)} ${e.clientWidth}px < ${e.scrollWidth}px`])
  }
  if (document.documentElement.scrollWidth > innerWidth + 1)
    found.push(['page scrolls sideways', `${document.documentElement.scrollWidth}px > ${innerWidth}px`])
  return found
}

const findings = new Map() // fault -> states it appeared in
async function check(page, state) {
  const faults = await page.evaluate(layoutFaults)
  await page.addScriptTag({ content: AXE })
  const axe = await page.evaluate(async () => (await window.axe.run(document, { runOnly: ['wcag2a', 'wcag2aa'], resultTypes: ['violations'] }))
    .violations.map(v => [`axe ${v.id}`, v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(' | ')]))
  for (const [what, where] of [...faults, ...axe]) {
    const key = `${what}: ${where}`
    findings.set(key, [...(findings.get(key) || []), state])
  }
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${state.replace(/[^a-z0-9]+/gi, '_')}.png` })
}

const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {})
for (const [width, height, device] of [[1400, 900, 'desktop'], [390, 844, 'phone']]) {
  for (const theme of ['Light', 'Dark']) {
    const page = await browser.newPage({ viewport: { width, height } })
    const errors = []
    page.on('pageerror', e => errors.push(String(e)))
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
    const openNav = async () => {
      const toggle = page.locator('.nav-toggle')
      if (device === 'phone' && await toggle.getAttribute('aria-expanded') !== 'true') { await toggle.click(); await page.waitForTimeout(250) }
    }
    await page.goto(BASE)
    await check(page, `${device} ${theme} landing`)
    await page.setInputFiles('#fileInput', SAMPLE)
    await page.waitForSelector('.sb-item', { state: 'attached', timeout: 60000 })
    await page.waitForTimeout(1000)
    await openNav()
    await page.locator('.sb-theme button', { hasText: theme }).click()
    const views = await page.locator('.sb-item .sb-item-label').allTextContents()
    for (const view of views) {
      await openNav()
      await page.locator('.sb-item', { hasText: view }).first().click()
      await page.waitForTimeout(800)
      if (view === 'Compare') {
        await page.setInputFiles('#compareFileInput', earlierFile())
        await page.getByRole('button', { name: 'Compare a different file' }).waitFor({ timeout: 60000 })
      }
      await check(page, `${device} ${theme} ${view}`)
      if (view === 'Gantt chart') {
        for (const [label, sel] of [['key dates', 'button[aria-label^="Edit key dates"]'], ['save view', '.vw-open']]) {
          await page.locator(sel).first().click()
          await page.waitForTimeout(300)
          await check(page, `${device} ${theme} Gantt ${label} panel`)
          await page.locator(sel).first().click()
        }
      }
    }
    await openNav()
    await page.getByRole('button', { name: /^Export/ }).click()
    await page.waitForTimeout(300)
    await check(page, `${device} ${theme} Export menu`)
    for (const e of errors) findings.set(`console error: ${e.slice(0, 200)}`, [`${device} ${theme}`])
    await page.close()
  }
}
await browser.close()

for (const [fault, states] of findings) console.log(`✗ ${fault}\n    in ${states.length} state(s): ${states.slice(0, 4).join('; ')}`)
console.log(findings.size ? `\n${findings.size} UI finding(s).` : 'UI audit: no findings.')
process.exit(findings.size ? 1 : 0)
