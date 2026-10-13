import { orderSeries } from './parties'

export function monthLabel(m, long = false) {
  const d = new Date(`${m}-15T12:00:00`)
  return d.toLocaleDateString('en-CA', long ? { month: 'long', year: 'numeric' } : { month: 'short', year: '2-digit' })
}

/** Turn the API response into one row per month: { month, total, <series>: value }. */
export function toRows(trend, measure) {
  if (!trend?.months?.length) return { rows: [], keys: [] }
  const keys = orderSeries(Object.keys(trend.series), trend.group_by)
  const rows = trend.months.map((month, i) => {
    const row = { month, total: trend.totals[i] }
    for (const k of keys) {
      const count = trend.series[k][i]
      row[k] = measure === 'share' ? (trend.totals[i] ? (count / trend.totals[i]) * 100 : 0) : count
    }
    return row
  })
  return { rows, keys }
}
