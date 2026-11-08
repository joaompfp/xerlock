// The lifecycle of one "read a schedule file" job, as an explicit state machine.
//
//   idle ──start──▶ parsing ──succeed──▶ idle
//                      │  ▲
//                      │  └── start (a newer file supersedes: run + 1)
//                      └─fail──▶ failed ──start/dismiss──▶ parsing / idle
//
// Every event after `start` carries the `run` it belongs to. A parse that outlives the
// file that replaced it reports back with an old run and is ignored, so a slow first
// file can never switch off the spinner of the second or overwrite its result.
//
// Pure on purpose: no Vue, no timers, no I/O. The component owns those and feeds events in.

export type LoadPhase = 'idle' | 'parsing' | 'failed'

export interface LoadState {
  phase: LoadPhase
  /** Which job this state belongs to; bumped by every `start`. */
  run: number
  /** Latest progress line from the parser ('' until it says something). */
  note: string
  /** Index into the rotating stage messages, advanced by `tick`. */
  stage: number
  /** What went wrong, only while phase is 'failed'. */
  error: string | null
}

export type LoadEvent =
  | { type: 'start' }
  | { type: 'note'; run: number; text: string }
  | { type: 'tick'; run: number }
  | { type: 'succeed'; run: number }
  | { type: 'fail'; run: number; message: string }
  | { type: 'dismiss' }

export const initialLoad: LoadState = { phase: 'idle', run: 0, note: '', stage: 0, error: null }

export function loadReducer(state: LoadState, event: LoadEvent): LoadState {
  if (event.type === 'start') {
    return { phase: 'parsing', run: state.run + 1, note: '', stage: 0, error: null }
  }
  if (event.type === 'dismiss') {
    return state.phase === 'failed' ? { ...state, phase: 'idle', error: null } : state
  }
  // Everything else only means something for the job that is parsing right now.
  if (state.phase !== 'parsing' || event.run !== state.run) return state
  switch (event.type) {
    case 'note': return { ...state, note: event.text }
    case 'tick': return { ...state, stage: state.stage + 1 }
    case 'succeed': return { ...state, phase: 'idle' }
    case 'fail': return { ...state, phase: 'failed', error: event.message }
  }
}
