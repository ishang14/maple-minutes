import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { monthLabel, toRows } from '../lib/trend'
import TrendChart from './TrendChart'

beforeAll(() => {
  // Recharts measures its container; jsdom has no layout, so give it a ResizeObserver that never fires.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})

const BY_PARTY = {
  query: 'carbon tax',
  group_by: 'party',
  months: ['2023-01', '2023-02', '2023-03'],
  totals: [100, 200, 0],
  series: { Liberal: [10, 40, 0], Conservative: [20, 20, 0], 'Independent': [1, 0, 0] },
}

const OVERALL = {
  query: '', group_by: 'none', months: ['2023-01', '2023-02'], totals: [100, 50], series: { all: [5, 25] },
}

describe('toRows', () => {
  it('builds one row per month with counts, in the fixed party order (unknown last)', () => {
    const { rows, keys } = toRows(BY_PARTY, 'count')
    expect(keys).toEqual(['Conservative', 'Liberal', 'Independent'])
    expect(rows[1]).toEqual({ month: '2023-02', total: 200, Conservative: 20, Liberal: 40, Independent: 0 })
  })

  it('converts to a percentage share and treats an empty month as 0, not NaN', () => {
    const { rows } = toRows(BY_PARTY, 'share')
    expect(rows[0].Liberal).toBeCloseTo(10)
    expect(rows[1].Liberal).toBeCloseTo(20)
    expect(rows[2].Liberal).toBe(0)
  })

  it('returns nothing for an empty response', () => {
    expect(toRows({ months: [], totals: [], series: {} }, 'count')).toEqual({ rows: [], keys: [] })
    expect(toRows(null, 'count')).toEqual({ rows: [], keys: [] })
  })

  it('formats month labels without timezone drift', () => {
    expect(monthLabel('2023-01', true)).toMatch(/January 2023/)
    expect(monthLabel('2023-12')).toMatch(/Dec/)
  })
})

describe('TrendChart', () => {
  it('fetches with the submitted query and filters, and shows the title', async () => {
    const fetchTrend = vi.fn().mockResolvedValue(OVERALL)
    render(<TrendChart query="carbon tax" filters={{ party: 'NDP' }} fetchTrend={fetchTrend} />)
    expect(await screen.findByRole('heading', { name: '“carbon tax” over time' })).toBeInTheDocument()
    await waitFor(() => expect(fetchTrend).toHaveBeenCalled())
    expect(fetchTrend.mock.calls[0][0]).toEqual({ query: 'carbon tax', groupBy: 'none', filters: { party: 'NDP' } })
    expect(screen.getByRole('img', { name: /Line chart of monthly speeches, January 2023 to February 2023/ })).toBeInTheDocument()
  })

  it('has no legend for one series but gives a legend for several', async () => {
    const fetchTrend = vi.fn().mockResolvedValueOnce(OVERALL).mockResolvedValue(BY_PARTY)
    render(<TrendChart query="" filters={{}} fetchTrend={fetchTrend} />)
    await screen.findByRole('img')
    expect(screen.queryByRole('list', { name: 'Legend' })).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Split by'), 'party')
    const legend = await screen.findByRole('list', { name: 'Legend' })
    expect(within(legend).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Conservative', 'Liberal', 'Independent',
    ])
    expect(fetchTrend).toHaveBeenLastCalledWith(expect.objectContaining({ groupBy: 'party' }), expect.anything())
  })

  it('offers the same numbers as a table, switching between count and share', async () => {
    render(<TrendChart query="carbon tax" filters={{}} fetchTrend={vi.fn().mockResolvedValue(BY_PARTY)} />)
    await screen.findByRole('img')
    await userEvent.click(screen.getByRole('button', { name: 'Show table' }))
    const table = screen.getByRole('table')
    const feb = within(table).getByRole('row', { name: /February 2023/ })
    expect(within(feb).getAllByRole('cell').map((c) => c.textContent)).toEqual(['20', '40', '0', '200'])
    await userEvent.selectOptions(screen.getByLabelText('Measure'), 'share')
    expect(within(screen.getByRole('row', { name: /February 2023/ })).getAllByRole('cell')[1]).toHaveTextContent('20.0%')
    await userEvent.click(screen.getByRole('button', { name: 'Show chart' }))
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('says so when nothing matches, and shows the server error otherwise', async () => {
    const empty = { query: 'x', group_by: 'none', months: [], totals: [], series: {} }
    const { unmount } = render(<TrendChart query="x" filters={{}} fetchTrend={vi.fn().mockResolvedValue(empty)} />)
    expect(await screen.findByText('No speeches match these filters.')).toBeInTheDocument()
    unmount()
    render(<TrendChart query="x" filters={{}} fetchTrend={vi.fn().mockRejectedValue(new Error('Server is down.'))} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the trend. Server is down.')
  })

  it('keeps the previous chart on screen while new data loads', async () => {
    let release
    const fetchTrend = vi.fn()
      .mockResolvedValueOnce(OVERALL)
      .mockImplementationOnce(() => new Promise((r) => (release = r)))
    const { rerender } = render(<TrendChart query="a" filters={{}} fetchTrend={fetchTrend} />)
    await screen.findByRole('img')
    rerender(<TrendChart query="b" filters={{}} fetchTrend={fetchTrend} />)
    await waitFor(() => expect(screen.getByRole('img').parentElement).toHaveAttribute('aria-busy', 'true'))
    expect(screen.getByRole('img')).toBeInTheDocument() // no flash to an empty state
    release(OVERALL)
    await waitFor(() => expect(screen.getByRole('img').parentElement).toHaveAttribute('aria-busy', 'false'))
  })
})
