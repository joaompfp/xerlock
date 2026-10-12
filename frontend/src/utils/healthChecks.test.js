import { describe, it, expect } from 'vitest'
import sample from './fixtures/sample-schedule.json'
import { runChecks, defaultConfig, weightedScore } from './healthChecks'

// Fixture: the backend's parse of examples/sample-schedule.xer (project + activities).
// tests/test_fixture.py fails when it drifts from the parser; it prints how to regenerate.
const counts = r => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, v.count]))

describe('runChecks on the sample schedule', () => {
  const out = runChecks(sample, defaultConfig())

  it('produces the pinned finding counts', () => {
    expect(counts(out.results)).toMatchInlineSnapshot(`
      {
        "alap": 0,
        "driving": 0,
        "fs": 93,
        "hardcstr": 0,
        "highdur": 2,
        "highfloat": 5,
        "invdates": 0,
        "lags": 0,
        "leads": 0,
        "loe": 0,
        "missed": 1,
        "negfloat": 0,
        "noresource": 0,
        "oos": 2,
        "openends": 0,
      }
    `)
  })

  it('scores', () => {
    expect(weightedScore(out.results, defaultConfig())).toMatchInlineSnapshot(`75`)
  })
})
