import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { EMPTY_FILTERS } from '../lib/filters'
import FilterPanel from './FilterPanel'
import ResultsList from './ResultsList'

const RESULT = {
  n: 1,
  chunk_id: 'a',
  speaker: 'Mrs. Tracy Gray',
  party: 'Conservative',
  date: '2023-02-07',
  heading: 'Carbon Pricing',
  bill: null,
  domains: ['finance_economy'],
  text: 'The full carbon tax speech, all of it.',
  snippet: 'The <mark>carbon</mark> <mark>tax</mark> &lt;b&gt;is&lt;/b&gt; a burden',
  source_url: 'https://example.test/s#Int-1',
}

describe('ResultsList', () => {
  it('renders highlighted snippets (escaped by the server) and an official link', () => {
    const { container } = render(<ResultsList results={[RESULT]} />)
    expect(container.querySelectorAll('mark')).toHaveLength(2)
    expect(container.querySelector('b')).toBeNull() // the escaped <b> stays text
    expect(screen.getByText(/<b>is<\/b>/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Official Hansard/ })).toHaveAttribute('href', RESULT.source_url)
  })

  it('expands to the full speech and back to the snippet', async () => {
    render(<ResultsList results={[RESULT]} />)
    await userEvent.click(screen.getByRole('button', { name: 'Read full speech' }))
    expect(screen.getByText('The full carbon tax speech, all of it.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show less' }))
    expect(screen.queryByText('The full carbon tax speech, all of it.')).not.toBeInTheDocument()
  })
})

const OPTIONS = {
  parties: ['Conservative', 'Liberal'],
  parliaments: [43, 44, 45],
  date_min: '2019-12-05',
  date_max: '2026-10-09',
  domains: [{ id: 'law_security', label: 'Law, justice and national security' }],
}

function PanelHarness({ fetchSpeakers, onChange }) {
  const [value, setValue] = useState(EMPTY_FILTERS)
  return (
    <FilterPanel
      options={OPTIONS}
      value={value}
      fetchSpeakers={fetchSpeakers}
      onChange={(v) => {
        setValue(v)
        onChange?.(v)
      }}
    />
  )
}

describe('FilterPanel', () => {
  it('sets party, parliament, dates and topics', async () => {
    const onChange = vi.fn()
    render(<PanelHarness fetchSpeakers={vi.fn()} onChange={onChange} />)
    await userEvent.selectOptions(screen.getByLabelText('Party'), 'Liberal')
    await userEvent.selectOptions(screen.getByLabelText('Parliament'), '44')
    await userEvent.type(screen.getByLabelText('From'), '2023-01-01')
    await userEvent.click(screen.getByRole('checkbox', { name: /Law, justice/ }))
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ party: 'Liberal', parliament: '44', date_from: '2023-01-01', domains: ['law_security'] }),
    )
    await userEvent.click(screen.getByRole('checkbox', { name: /Law, justice/ }))
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ domains: [] }))
  })

  it('offers MP name suggestions after a short pause and applies the chosen one', async () => {
    const fetchSpeakers = vi.fn().mockResolvedValue(['Hon. Pierre Poilievre'])
    const onChange = vi.fn()
    render(<PanelHarness fetchSpeakers={fetchSpeakers} onChange={onChange} />)
    await userEvent.type(screen.getByRole('combobox', { name: 'Member of Parliament' }), 'poil')
    const option = await screen.findByRole('option', { name: 'Hon. Pierre Poilievre' })
    expect(fetchSpeakers).toHaveBeenCalledTimes(1) // debounced: one call, not one per key
    expect(fetchSpeakers).toHaveBeenCalledWith('poil', expect.anything())
    await userEvent.click(option)
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ speaker: 'Hon. Pierre Poilievre' }))
    expect(screen.getByRole('combobox', { name: 'Member of Parliament' })).toHaveValue('Hon. Pierre Poilievre')
  })

  it('supports the keyboard: arrows then Enter pick a suggestion', async () => {
    const fetchSpeakers = vi.fn().mockResolvedValue(['Anna Lee', 'Ann Marie Cho'])
    const onChange = vi.fn()
    render(<PanelHarness fetchSpeakers={fetchSpeakers} onChange={onChange} />)
    await userEvent.type(screen.getByRole('combobox', { name: 'Member of Parliament' }), 'ann')
    await screen.findByRole('listbox')
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ speaker: 'Ann Marie Cho' }))
  })

  it('clears the name filter when the name is edited, and Reset clears everything', async () => {
    const fetchSpeakers = vi.fn().mockResolvedValue(['Anna Lee'])
    const onChange = vi.fn()
    render(<PanelHarness fetchSpeakers={fetchSpeakers} onChange={onChange} />)
    const box = screen.getByRole('combobox', { name: 'Member of Parliament' })
    await userEvent.type(box, 'ann')
    await userEvent.click(await screen.findByRole('option', { name: 'Anna Lee' }))
    await userEvent.type(box, 'x')
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ speaker: '' }))

    await userEvent.selectOptions(screen.getByLabelText('Party'), 'Liberal')
    await userEvent.click(screen.getByRole('button', { name: 'Reset filters' }))
    expect(onChange).toHaveBeenLastCalledWith(EMPTY_FILTERS)
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Member of Parliament' })).toHaveValue(''))
    expect(screen.getByLabelText('Party')).toHaveValue('')
  })

  it('does not search for names shorter than two letters', async () => {
    const fetchSpeakers = vi.fn().mockResolvedValue([])
    render(<PanelHarness fetchSpeakers={fetchSpeakers} />)
    await userEvent.type(screen.getByRole('combobox', { name: 'Member of Parliament' }), 'a')
    await new Promise((r) => setTimeout(r, 400))
    expect(fetchSpeakers).not.toHaveBeenCalled()
  })
})
