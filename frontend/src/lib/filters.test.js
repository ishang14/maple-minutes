import { describe, expect, it } from 'vitest'
import { EMPTY_FILTERS, normalizeBill } from './filters'

describe('normalizeBill', () => {
  it.each([
    ['C-21', 'C-21'],
    ['c21', 'C-21'],
    ['C 21', 'C-21'],
    ['Bill C-21', 'C-21'],
    ['bill   s-3', 'S-3'],
    ['C‑5', 'C-5'], // non-breaking hyphen
    ['C-021', 'C-21'],
    ['  C-9  ', 'C-9'],
  ])('turns %j into %j', (input, expected) => {
    expect(normalizeBill(input)).toBe(expected)
  })

  it('returns an empty string for empty input (no filter)', () => {
    expect(normalizeBill('')).toBe('')
    expect(normalizeBill('   ')).toBe('')
    expect(normalizeBill(undefined)).toBe('')
  })

  it.each(['C-', '21', 'Bill', 'CC-1', 'C-1234', 'D-5', 'carbon'])('rejects %j', (input) => {
    expect(normalizeBill(input)).toBeNull()
  })

  it('has a bill field in the empty filter set', () => {
    expect(EMPTY_FILTERS).toHaveProperty('bill', '')
  })
})
