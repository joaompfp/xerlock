import { describe, it, expect } from 'vitest'
import { formatDate, formatDateShort, dateFormat } from './format'

// The shared formatters print what toLocaleDateString printed, except that September is
// "Sep" like the other three-letter months.
describe('date formatting', () => {
  const inputs: (string | number | Date)[] = [
    '2026-03-02T08:00:00', '2026-12-31T23:59:00', '2027-01-01', 1767225600000,
    new Date(2026, 1, 28), '2026-02-29T00:00:00', 'not a date',
  ]
  it('matches toLocaleDateString, invalid dates included', () => {
    for (const d of inputs) {
      expect(formatDate(d)).toBe(new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).replace('Sept', 'Sep'))
      expect(formatDateShort(d)).toBe(new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }).replace('Sept', 'Sep'))
    }
  })
  it('keeps the empty markers', () => {
    expect(formatDate(null)).toBe('--')
    expect(formatDateShort('')).toBe('—')
  })
  it('answers a repeated date from its cache, and a Date by its time', () => {
    const f = dateFormat({ month: 'short' })
    expect(f(new Date(2026, 4, 3))).toBe('May')
    expect(f(new Date(2026, 4, 3))).toBe('May')
    expect(f(new Date(2026, 5, 3))).toBe('Jun')
  })
  it('writes September with three letters', () => {
    expect(formatDate('2026-09-08')).toBe('08 Sep 2026')
    expect(dateFormat({ month: 'short' })(new Date(2026, 8, 1))).toBe('Sep')
  })
})
