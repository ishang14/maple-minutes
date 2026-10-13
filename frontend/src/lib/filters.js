export const EMPTY_FILTERS = {
  date_from: '',
  date_to: '',
  party: '',
  speaker: '',
  parliament: '',
  bill: '',
  domains: [],
}

/**
 * Canonical bill number from what a person types: "c21", "C 21", "Bill C-21" -> "C-21".
 * Returns '' for empty input and null when the text is not a bill number (C-n or S-n).
 */
export function normalizeBill(text) {
  const t = String(text ?? '')
    .trim()
    .replace(/^bill\s+/i, '')
  if (!t) return ''
  const m = /^([cs])\s*[-‐-―]?\s*(\d{1,3})$/i.exec(t)
  return m ? `${m[1].toUpperCase()}-${Number(m[2])}` : null
}
