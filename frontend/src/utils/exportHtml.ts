// A page section saved as one self-contained HTML file: the section's markup with the
// page's own styles inlined, so it opens anywhere (an email attachment, a shared drive)
// looking as it does here. Light theme; elements marked .no-export (buttons, links into
// the app) are left out; web fonts fall back to the system's, since their files are not
// carried along.

function pageCss(): string {
  const out: string[] = []
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList
    try { rules = sheet.cssRules } catch { continue } // a cross-origin sheet: unreadable, skip
    for (const rule of Array.from(rules)) {
      if (rule instanceof CSSFontFaceRule) continue
      out.push(rule.cssText)
    }
  }
  return out.join('\n')
}

const escapeHtml = (s: string) => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))

export function standaloneHtml(el: HTMLElement, title: string): string {
  const clone = el.cloneNode(true) as HTMLElement
  clone.querySelectorAll('.no-export').forEach(n => n.remove())
  return '<!doctype html>\n<html lang="en" data-theme="light"><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width, initial-scale=1">' +
    `<title>${escapeHtml(title)}</title><style>${pageCss()}\nbody{margin:0;padding:24px;background:#fff}</style></head>` +
    `<body>${clone.outerHTML}</body></html>`
}

export function downloadFile(name: string, text: string, type = 'text/html'): void {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
