import { describe, it, expect } from 'vitest'
import { unsupportedFileMessage } from './source'

describe('unsupportedFileMessage', () => {
  it('lets the readable formats through, any case', () => {
    expect(unsupportedFileMessage('Programme.XER')).toBeNull()
    expect(unsupportedFileMessage('plan.xml')).toBeNull()
    expect(unsupportedFileMessage('plan.mpp')).toBeNull()
  })
  it('says how to export an Asta file, and refuses others plainly', () => {
    expect(unsupportedFileMessage('site.pp')).toMatch(/Powerproject.*Microsoft Project XML/)
    expect(unsupportedFileMessage('notes.pdf')).toMatch(/^Only \.xer/)
  })
})
