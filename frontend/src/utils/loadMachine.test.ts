import { describe, expect, it } from 'vitest'
import { initialLoad, loadReducer, type LoadState } from './loadMachine'

const started = (s: LoadState = initialLoad) => loadReducer(s, { type: 'start' })

describe('loadReducer', () => {
  it('starts idle with nothing to show', () => {
    expect(initialLoad).toEqual({ phase: 'idle', run: 0, note: '', stage: 0, error: null })
  })

  it('start moves to parsing and clears the previous note, stage and error', () => {
    const failed: LoadState = { phase: 'failed', run: 3, note: 'old', stage: 2, error: 'boom' }
    expect(started(failed)).toEqual({ phase: 'parsing', run: 4, note: '', stage: 0, error: null })
  })

  it('note and tick update the parsing progress of the current run', () => {
    let s = started()
    s = loadReducer(s, { type: 'note', run: s.run, text: 'Reading XER tables…' })
    s = loadReducer(s, { type: 'tick', run: s.run })
    s = loadReducer(s, { type: 'tick', run: s.run })
    expect(s).toMatchObject({ phase: 'parsing', note: 'Reading XER tables…', stage: 2 })
  })

  it('succeed returns to idle', () => {
    const s = started()
    expect(loadReducer(s, { type: 'succeed', run: s.run })).toMatchObject({ phase: 'idle', error: null })
  })

  it('fail keeps the message until the next start or a dismiss', () => {
    const s = started()
    const failed = loadReducer(s, { type: 'fail', run: s.run, message: 'bad file' })
    expect(failed).toMatchObject({ phase: 'failed', error: 'bad file' })
    expect(loadReducer(failed, { type: 'dismiss' })).toMatchObject({ phase: 'idle', error: null })
    expect(started(failed)).toMatchObject({ phase: 'parsing', error: null })
  })

  it('a second start supersedes the first: late events of the old run are ignored', () => {
    const first = started()
    const second = started(first)
    expect(second.run).toBe(first.run + 1)
    // The first parse finishes (or fails) after the second began.
    expect(loadReducer(second, { type: 'succeed', run: first.run })).toBe(second)
    expect(loadReducer(second, { type: 'fail', run: first.run, message: 'x' })).toBe(second)
    expect(loadReducer(second, { type: 'note', run: first.run, text: 'x' })).toBe(second)
    expect(loadReducer(second, { type: 'tick', run: first.run })).toBe(second)
  })

  it('events that arrive when nothing is parsing change nothing', () => {
    const s = started()
    const done = loadReducer(s, { type: 'succeed', run: s.run })
    expect(loadReducer(done, { type: 'tick', run: s.run })).toBe(done)
    expect(loadReducer(done, { type: 'note', run: s.run, text: 'late' })).toBe(done)
    expect(loadReducer(done, { type: 'fail', run: s.run, message: 'late' })).toBe(done)
  })

  it('dismiss never interrupts a parse', () => {
    const s = started()
    expect(loadReducer(s, { type: 'dismiss' })).toBe(s)
  })
})
