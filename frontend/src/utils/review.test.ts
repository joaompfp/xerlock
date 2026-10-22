import { describe, it, expect } from 'vitest'
import fixture from './fixtures/sample-schedule.json'
import type { Schedule } from '../types/schedule'
import { buildReview } from './review'
import { defaultConfig, runChecks, weightedScore } from './healthChecks'

const sample = fixture as unknown as Schedule

describe('buildReview', () => {
  const cfg = defaultConfig()
  const r = buildReview(sample, cfg, {}, null)

  it('states what the file is and its headline figures', () => {
    expect(r.kind).toBe('P6 .xer export')
    expect(r.activities).toBe(24)
    expect(r.complete).toBe(3)
    expect(r.longestPath).toBe(sample.project.total_longest_path)
  })
  it('gives the same score as the Health check, and the losses that make it', () => {
    expect(r.score).toBe(weightedScore(runChecks(sample, cfg).results, cfg))
    expect(Math.round(100 - r.pointsLost)).toBe(r.score)
    const lost = r.findings.map(f => f.pointsLost)
    expect(lost).toEqual([...lost].sort((a, b) => b - a))
    expect(r.findings[0].measure).toMatch(/target/)
  })
  it('lists the milestones ahead and the reviewer’s notes', () => {
    expect(r.milestonesAhead.every(m => !m.achieved)).toBe(true)
    const noted = buildReview(sample, cfg, { [sample.activities[0].task_id]: { note: 'Check this', severity: 'risk', updatedAt: 1 } }, null)
    expect(noted.notes).toEqual([{ code: sample.activities[0].task_code, name: sample.activities[0].task_name, severity: 'risk', note: 'Check this' }])
  })
  it('reads a comparison like the Compare view', () => {
    const same = buildReview(sample, cfg, {}, sample)
    expect(same.compare?.finishDeltaDays).toBe(0)
    expect(same.compare?.verdict.cls).toBe('v-hold')
    expect(same.compare?.longestPathKept).toBe(`${sample.project.total_longest_path}/${sample.project.total_longest_path}`)
  })
})
