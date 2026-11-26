import { describe, it, expect } from 'vitest'
import { formatDate, formatDateShort, dateFormat } from './format'

// The app prints dates the way P6 does: DD-MMM-YY (02-Mar-26). Day first, month by
// name, two-digit year, hyphens — so no date can be read as month-first.
describe('date formatting', () => {
  it('prints DD-MMM-YY', () => {
    expect(formatDate(new Date(2026, 2, 2))).toBe('02-Mar-26')
    expect(formatDate('2026-09-08T08:00:00')).toBe('08-Sep-26')
    expect(formatDate('2027-01-01T00:00:00')).toBe('01-Jan-27')
  })
  it('prints DD-MMM for the short form', () => {
    expect(formatDateShort(new Date(2026, 4, 3))).toBe('03-May')
    expect(formatDateShort('2026-12-31T23:59:00')).toBe('31-Dec')
  })
  it('keeps the two-digit year across the century', () => {
    expect(formatDate(new Date(2099, 11, 31))).toBe('31-Dec-99')
    expect(formatDate(new Date(2005, 0, 9))).toBe('09-Jan-05')
  })
  it('reads a bare calendar day as that day, not as UTC midnight', () => {
    // new Date('2026-11-25') is UTC midnight; read back west of UTC it is the 24th.
    expect(formatDate('2026-11-25')).toBe('25-Nov-26')
    expect(formatDateShort('2026-01-01')).toBe('01-Jan')
    expect(dateFormat({ day: 'numeric' })('2026-11-25')).toBe('25')
  })
  it('rejects a bare day that does not exist instead of rolling it over', () => {
    expect(formatDate('2026-02-30')).toBe('Invalid Date')
    expect(formatDate('2026-13-01')).toBe('Invalid Date')
  })
  it('leaves a string that carries a time to the Date constructor', () => {
    expect(formatDate('2026-11-25T08:00:00')).toBe('25-Nov-26')
    expect(formatDate('2026-11-25 08:00')).toBe('25-Nov-26')
  })
  it('keeps the empty and invalid markers', () => {
    expect(formatDate(null)).toBe('--')
    expect(formatDateShort('')).toBe('—')
    expect(formatDate('not a date')).toBe('Invalid Date')
    expect(formatDateShort('not a date')).toBe('Invalid Date')
  })
  it('answers a repeated date from its cache, and a Date by its time', () => {
    const f = dateFormat({ month: 'short' })
    expect(f(new Date(2026, 4, 3))).toBe('May')
    expect(f(new Date(2026, 4, 3))).toBe('May')
    expect(f(new Date(2026, 5, 3))).toBe('Jun')
  })
  it('writes September with three letters', () => {
    expect(formatDate('2026-09-08T08:00:00')).toBe('08-Sep-26')
    expect(dateFormat({ month: 'short' })(new Date(2026, 8, 1))).toBe('Sep')
  })
})
