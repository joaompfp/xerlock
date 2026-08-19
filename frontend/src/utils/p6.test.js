import { describe, it, expect } from 'vitest'
import {
  relTypeLabel, cstrLabel, HARD_CONSTRAINT_TYPES, displayStart, displayEnd,
} from './p6'
import { formatFloat, formatHours, formatLag, isMilestone } from './format'
import { PAPER_SIZES, paperOrDefault, usableWidthPx, usableHeightPx } from './paper'

describe('display-date convention', () => {
  // P6 resets the early dates of finished work to the data date. Rendering early
  // dates alone collapses every completed activity to a zero-width bar sitting on
  // the data date — the bug this convention exists to prevent.
  const completed = {
    act_start: '2026-01-21 08:00:00', act_end: '2026-01-30 16:00:00',
    early_start: '2026-03-02 08:00:00', early_end: '2026-03-02 08:00:00',
  }
  const notStarted = {
    act_start: null, act_end: null,
    early_start: '2026-04-01 08:00:00', early_end: '2026-04-10 16:00:00',
  }
  const inProgress = {
    act_start: '2026-02-23 08:00:00', act_end: null,
    early_start: '2026-03-02 08:00:00', early_end: '2026-03-19 16:00:00',
  }

  it('prefers actual dates once work has happened', () => {
    expect(displayStart(completed)).toBe(completed.act_start)
    expect(displayEnd(completed)).toBe(completed.act_end)
  })

  it('uses early dates for work that has not started', () => {
    expect(displayStart(notStarted)).toBe(notStarted.early_start)
    expect(displayEnd(notStarted)).toBe(notStarted.early_end)
  })

  it('mixes actual start with forecast finish for in-progress work', () => {
    expect(displayStart(inProgress)).toBe(inProgress.act_start)
    expect(displayEnd(inProgress)).toBe(inProgress.early_end)
  })

  it('gives a completed activity a non-zero span', () => {
    expect(new Date(displayEnd(completed)) - new Date(displayStart(completed))).toBeGreaterThan(0)
  })
})

describe('relationship and constraint labels', () => {
  it('translates P6 codes rather than showing them raw', () => {
    expect(relTypeLabel('PR_FS')).toBe('FS')
    expect(relTypeLabel('PR_SF')).toBe('SF')
    expect(cstrLabel('CS_MEO')).not.toBe('CS_MEO')
  })

  it('falls back to the raw code for anything unrecognised', () => {
    expect(relTypeLabel('PR_WAT')).toBe('PR_WAT')
    expect(cstrLabel('CS_FUTURE')).toBe('CS_FUTURE')
  })

  it('classifies mandatory constraints as hard', () => {
    // Hard constraints override network logic and can manufacture negative float,
    // so the Health Check severity depends on this set being right.
    expect(HARD_CONSTRAINT_TYPES.has('CS_MANDSTART')).toBe(true)
    expect(HARD_CONSTRAINT_TYPES.has('CS_MANDFIN')).toBe(true)
    expect(HARD_CONSTRAINT_TYPES.has('CS_ALAP')).toBe(false)
  })
})

describe('float, duration and lag are shown in working days', () => {
  it('converts hours to days using the activity calendar, not a fixed 8', () => {
    expect(formatFloat(80, 8)).toBe('10d')
    expect(formatFloat(80, 10)).toBe('8d')
  })

  it('keeps the sign on negative float', () => {
    expect(formatFloat(-8, 8)).toBe('-1d')
  })

  it('distinguishes zero float from unknown float', () => {
    // Zero means critical; blank means P6 gave us nothing. They must not collapse.
    expect(formatFloat(0, 8)).toBe('0d')
    expect(formatFloat(null, 8)).toBe('—')
  })

  it('formats lags in days with an explicit sign', () => {
    expect(formatLag(40, 8)).toBe('+5d')
    expect(formatLag(-8, 8)).toBe('-1d')
    expect(formatLag(0, 8)).toBe('')
  })

  it('renders durations in days', () => {
    expect(formatHours(80, 8)).toBe('10d')
  })
})

describe('milestone detection', () => {
  it('recognises both start and finish milestones', () => {
    expect(isMilestone({ task_type: 'TT_Mile' })).toBe(true)
    expect(isMilestone({ task_type: 'TT_FinMile' })).toBe(true)
    expect(isMilestone({ task_type: 'TT_Task' })).toBe(false)
  })
})

describe('paper sizes', () => {
  it('exposes the CSS keywords @page requires', () => {
    expect(PAPER_SIZES.a4.pageCss).toBe('A4')
    expect(PAPER_SIZES.letter.pageCss).toBe('letter')
  })

  it('falls back to A4 for an unknown key', () => {
    expect(paperOrDefault('foolscap')).toBe(PAPER_SIZES.a4)
  })

  it('reproduces each chart\'s previously inlined arithmetic exactly', () => {
    // Guards the extraction: these are the values the two components computed
    // from their own copies before utils/paper.js existed.
    const gantt = (mm) => Math.round((mm - 20) * (96 / 25.4)) - 15
    const cp = (mm) => Math.round((mm - 20) * (96 / 25.4)) - 20
    for (const key of Object.keys(PAPER_SIZES)) {
      expect(usableWidthPx(key, 15)).toBe(gantt(PAPER_SIZES[key].wMm))
      expect(usableWidthPx(key, 20)).toBe(cp(PAPER_SIZES[key].wMm))
      expect(usableHeightPx(key, 20)).toBe(cp(PAPER_SIZES[key].hMm))
    }
  })

  it('gives A3 more usable width than A4', () => {
    expect(usableWidthPx('a3', 15)).toBeGreaterThan(usableWidthPx('a4', 15))
  })
})
