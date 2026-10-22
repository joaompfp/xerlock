import { describe, it, expect } from 'vitest'
import { visibleRowRange } from './virtual'

describe('visibleRowRange', () => {
  it('covers the viewport plus the overscan, clamped to the rows that exist', () => {
    expect(visibleRowRange(0, 260, 26, 1000, 5)).toEqual({ from: 0, to: 15 })
    expect(visibleRowRange(2600, 260, 26, 1000, 5)).toEqual({ from: 95, to: 115 })
    expect(visibleRowRange(2600, 260, 26, 30, 5)).toEqual({ from: 30, to: 30 })
    expect(visibleRowRange(0, 260, 26, 0, 5)).toEqual({ from: 0, to: 0 })
  })
})
