// Fixed colour per party / domain: colour follows the entity, so filtering never repaints the
// series that remain. The slot ORDER below is the order that passed the palette validator.
const PARTY_ORDER = ['NDP', 'Conservative', 'Bloc Québécois', 'Liberal', 'Green Party']

const PARTY_VAR = {
  NDP: '--c-ndp',
  Conservative: '--c-conservative',
  'Bloc Québécois': '--c-bloc',
  Liberal: '--c-liberal',
  'Green Party': '--c-green',
}

const DOMAIN_VAR = {
  finance_economy: '--c-finance',
  law_security: '--c-law',
  foreign_relations: '--c-foreign',
}

export const DOMAIN_LABELS = {
  law_security: 'Law, justice and national security',
  foreign_relations: 'Foreign relations',
  finance_economy: 'Finance, economy and taxation',
}

const DOMAIN_ORDER = ['finance_economy', 'law_security', 'foreign_relations']

/** CSS colour for a series key (a party name, a domain id, or "all"). */
export function seriesColor(key) {
  const v = PARTY_VAR[key] ?? DOMAIN_VAR[key] ?? (key === 'all' ? '--c-all' : '--c-other')
  return `var(${v})`
}

/** Series keys in their fixed legend/draw order; unknown keys (e.g. Independent) go last. */
export function orderSeries(keys, groupBy) {
  const order = groupBy === 'domain' ? DOMAIN_ORDER : groupBy === 'party' ? PARTY_ORDER : []
  const rank = (k) => (order.includes(k) ? order.indexOf(k) : order.length)
  return [...keys].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
}

export function seriesLabel(key) {
  return key === 'all' ? 'Matching speeches' : (DOMAIN_LABELS[key] ?? key)
}
