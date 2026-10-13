import { useEffect, useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getTrend } from '../api/client'
import { seriesColor, seriesLabel } from '../lib/parties'
import { monthLabel, toRows } from '../lib/trend'

const GROUPS = [
  { id: 'none', label: 'Overall' },
  { id: 'party', label: 'By party' },
  { id: 'domain', label: 'By topic' },
]

const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })

const fmtValue = (v, measure) => (measure === 'share' ? `${v.toFixed(1)}%` : v.toLocaleString('en'))

function ChartTooltip({ active, payload, label, measure }) {
  if (!active || !payload?.length) return null
  const rows = [...payload].sort((a, b) => b.value - a.value)
  return (
    <div
      className="rounded-md border px-3 py-2 text-xs shadow-md"
      style={{ background: 'var(--viz-surface)', borderColor: 'var(--viz-axis)', color: 'var(--viz-text)' }}
    >
      <p className="mb-1 font-medium" style={{ color: 'var(--viz-text-2)' }}>
        {monthLabel(label, true)}
      </p>
      {rows.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-3" style={{ background: seriesColor(p.dataKey) }} />
          <span className="font-semibold tabular-nums">{fmtValue(p.value, measure)}</span>
          <span style={{ color: 'var(--viz-text-2)' }}>{seriesLabel(p.dataKey)}</span>
        </p>
      ))}
    </div>
  )
}

function Legend({ keys }) {
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Legend">
      {keys.map((k) => (
        <li key={k} className="flex items-center gap-1.5" style={{ color: 'var(--viz-text-2)' }}>
          <span className="inline-block h-0.5 w-4" style={{ background: seriesColor(k) }} />
          {seriesLabel(k)}
        </li>
      ))}
    </ul>
  )
}

function DataTable({ rows, keys, measure }) {
  return (
    <div className="max-h-72 overflow-auto rounded-md border border-neutral-200 dark:border-neutral-800">
      <table className="w-full text-xs">
        <caption className="sr-only">Monthly values behind the chart</caption>
        <thead className="sticky top-0 bg-neutral-100 dark:bg-neutral-800">
          <tr>
            <th scope="col" className="px-2 py-1.5 text-left font-medium">Month</th>
            {keys.map((k) => (
              <th key={k} scope="col" className="px-2 py-1.5 text-right font-medium">{seriesLabel(k)}</th>
            ))}
            <th scope="col" className="px-2 py-1.5 text-right font-medium">All speeches</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.month} className="border-t border-neutral-200 dark:border-neutral-800">
              <th scope="row" className="px-2 py-1 text-left font-normal">{monthLabel(r.month, true)}</th>
              {keys.map((k) => (
                <td key={k} className="px-2 py-1 text-right tabular-nums">{fmtValue(r[k], measure)}</td>
              ))}
              <td className="px-2 py-1 text-right tabular-nums">{r.total.toLocaleString('en')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** How often the search topic appears over time, optionally split by party or topic. */
export default function TrendChart({ query, filters, fetchTrend = getTrend }) {
  const [groupBy, setGroupBy] = useState('none')
  const [measure, setMeasure] = useState('count')
  const [asTable, setAsTable] = useState(false)
  const [state, setState] = useState({ data: null, loading: true, error: null })

  const filterKey = JSON.stringify(filters)
  useEffect(() => {
    const ctl = new AbortController()
    setState((s) => ({ ...s, loading: true, error: null })) // keep the previous frame while loading
    fetchTrend({ query, groupBy, filters }, { signal: ctl.signal })
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((e) => {
        if (e?.name !== 'AbortError') setState((s) => ({ ...s, loading: false, error: e.message }))
      })
    return () => ctl.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, groupBy, filterKey, fetchTrend])

  const { rows, keys } = useMemo(() => toRows(state.data, measure), [state.data, measure])
  const empty = !state.loading && !state.error && rows.length === 0

  return (
    <section aria-labelledby="trend-title" className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="trend-title" className="text-base font-semibold">
            {query ? `“${query}” over time` : 'Debate volume over time'}
          </h2>
          <p className="text-xs text-neutral-600 dark:text-neutral-400">
            {measure === 'share' ? 'Share of speeches each month' : 'Speeches per month'} containing most of the words
            in your search, within the selected filters.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <select aria-label="Split by" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}
            className="rounded-md border border-neutral-300 bg-white px-2 py-1 dark:border-neutral-700 dark:bg-neutral-900">
            {GROUPS.map((g) => (
              <option key={g.id} value={g.id}>{g.label}</option>
            ))}
          </select>
          <select aria-label="Measure" value={measure} onChange={(e) => setMeasure(e.target.value)}
            className="rounded-md border border-neutral-300 bg-white px-2 py-1 dark:border-neutral-700 dark:bg-neutral-900">
            <option value="count">Count</option>
            <option value="share">Share of speeches</option>
          </select>
          <button type="button" onClick={() => setAsTable((t) => !t)} aria-pressed={asTable}
            className="rounded-md border border-neutral-300 px-2 py-1 font-medium dark:border-neutral-700">
            {asTable ? 'Show chart' : 'Show table'}
          </button>
        </div>
      </div>

      {state.error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-900 dark:bg-red-950/40 dark:text-red-200">
          Could not load the trend. {state.error}
        </p>
      )}
      {empty && <p className="py-10 text-center text-sm text-neutral-600 dark:text-neutral-400">No speeches match these filters.</p>}
      {state.loading && !state.data && <p role="status" className="py-10 text-center text-sm text-neutral-600">Loading trend…</p>}

      {rows.length > 0 && (
        <div className={state.loading ? 'opacity-50 transition-opacity' : 'transition-opacity'} aria-busy={state.loading}>
          {keys.length > 1 && <Legend keys={keys} />}
          {asTable ? (
            <DataTable rows={rows} keys={keys} measure={measure} />
          ) : (
            <div role="img" aria-label={`Line chart of monthly speeches, ${monthLabel(rows[0].month, true)} to ${monthLabel(rows.at(-1).month, true)}. Use the table view for exact values.`}
              className="h-64 w-full sm:h-72" style={{ background: 'var(--viz-surface)' }}>
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--viz-grid)" strokeWidth={1} />
                  <XAxis dataKey="month" tickFormatter={(m) => monthLabel(m)} minTickGap={36}
                    tick={{ fill: 'var(--viz-text-3)', fontSize: 11 }} axisLine={{ stroke: 'var(--viz-axis)' }} tickLine={false} />
                  <YAxis width={44} tickFormatter={(v) => (measure === 'share' ? `${v}%` : compact.format(v))}
                    tick={{ fill: 'var(--viz-text-3)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<ChartTooltip measure={measure} />} cursor={{ stroke: 'var(--viz-axis)', strokeWidth: 1 }} isAnimationActive={false} />
                  {keys.map((k) => (
                    <Line key={k} type="linear" dataKey={k} name={seriesLabel(k)} stroke={seriesColor(k)} strokeWidth={2}
                      strokeLinecap="round" strokeLinejoin="round" dot={false} isAnimationActive={false}
                      activeDot={{ r: 4, fill: seriesColor(k), stroke: 'var(--viz-surface)', strokeWidth: 2 }} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
