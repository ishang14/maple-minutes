import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

// The chart is covered in its own tests; here it only needs to receive the right props.
vi.mock('./components/TrendChart', () => ({
  default: ({ query, filters }) => <div data-testid="trend">{JSON.stringify({ query, filters })}</div>,
}))

const OPTIONS = {
  parties: ['Conservative', 'Liberal'],
  parliaments: [43, 44, 45],
  bills: ['C-21'],
  date_min: '2019-12-05',
  date_max: '2026-10-09',
  domains: [],
}

const SOURCES = [
  { n: 1, chunk_id: 'a', speaker: 'Jane Doe', party: 'Liberal', date: '2023-05-01', heading: 'Carbon Pricing',
    text: 'We will keep carbon pricing.', source_url: 'https://example.test/1', domains: [] },
  { n: 2, chunk_id: 'b', speaker: 'John Roe', party: 'Conservative', date: '2023-06-02', heading: 'Budget',
    text: 'Axe the tax.', source_url: 'https://example.test/2', domains: [] },
]

const streamOf = (events) => vi.fn(async function* () { for (const e of events) yield e })

const setup = (props = {}) => {
  const fetchFilters = vi.fn().mockResolvedValue(OPTIONS)
  render(<App fetchFilters={fetchFilters} {...props} />)
  return { fetchFilters }
}

describe('App', () => {
  it('starts with examples and the About section, and no chart yet', async () => {
    const { fetchFilters } = setup()
    expect(within(screen.getByRole('banner')).getByText('Minutes')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/What did Parliament actually say/)
    expect(screen.getByRole('heading', { name: 'About and limitations' })).toBeInTheDocument()
    expect(screen.queryByTestId('trend')).not.toBeInTheDocument()
    await waitFor(() => expect(fetchFilters).toHaveBeenCalled())
    await userEvent.click(screen.getByRole('button', { name: /carbon tax/ }))
    expect(screen.getByRole('searchbox')).toHaveValue('What did parties say about the carbon tax?')
  })

  it('does not submit a question shorter than two characters', async () => {
    const streamFn = streamOf([])
    setup({ streamFn })
    await userEvent.type(screen.getByRole('searchbox'), 'a')
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
    await userEvent.keyboard('{Enter}')
    expect(streamFn).not.toHaveBeenCalled()
  })

  it('Ask: sends query and filters, streams the answer, and chips open the cited source card', async () => {
    const streamFn = streamOf([
      { event: 'sources', data: { sources: SOURCES } },
      { event: 'token', data: { text: 'Liberals defended pricing [1], ' } },
      { event: 'token', data: { text: 'Conservatives opposed it [2].' } },
      { event: 'done', data: { cited: [1, 2], invalid_citations: [], unverified_quotes: [] } },
    ])
    setup({ streamFn })
    await userEvent.selectOptions(await screen.findByRole('option', { name: 'Liberal' }).then((o) => o.parentElement), 'Liberal')
    await userEvent.type(screen.getByRole('searchbox'), 'carbon pricing')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    expect(await screen.findByText(/Liberals defended pricing/)).toBeInTheDocument()
    expect(streamFn.mock.calls[0][0]).toEqual({ query: 'carbon pricing', party: 'Liberal' })
    expect(screen.getByTestId('trend')).toHaveTextContent('"query":"carbon pricing"')

    // sources start collapsed; clicking the [2] chip expands source 2 and links to the sitting
    const sources = screen.getByRole('list', { name: 'Sources' })
    expect(within(sources).queryByText('Axe the tax.')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Source 2: John Roe/ }))
    expect(within(sources).getByText('Axe the tax.')).toBeInTheDocument()
    expect(within(sources).getByRole('link', { name: /Open in the official Hansard/ })).toHaveAttribute('href', 'https://example.test/2')
    expect(within(sources).queryByText('We will keep carbon pricing.')).not.toBeInTheDocument()
  })

  it('Ask: shows the readable error and keeps the partial answer when the LLM fails', async () => {
    setup({
      streamFn: streamOf([
        { event: 'sources', data: { sources: SOURCES } },
        { event: 'token', data: { text: 'Partial answer' } },
        { event: 'error', data: { message: 'Groq rate limit reached (free tier). Please try again in a moment.' } },
      ]),
    })
    await userEvent.type(screen.getByRole('searchbox'), 'carbon pricing')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Groq rate limit reached')
    expect(screen.getByRole('alert')).toHaveTextContent('The answer above is incomplete.')
    expect(screen.getByText('Partial answer')).toBeInTheDocument()
  })

  it('Ask: tells the user when nothing matched', async () => {
    setup({
      streamFn: streamOf([
        { event: 'sources', data: { sources: [] } },
        { event: 'token', data: { text: "The retrieved debates don't cover this." } },
        { event: 'done', data: { cited: [], invalid_citations: [], unverified_quotes: [] } },
      ]),
    })
    await userEvent.type(screen.getByRole('searchbox'), 'something obscure')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByText(/No speeches matched your question and filters/)).toBeInTheDocument()
  })

  it('Search: lists results with highlights, and handles empty and error responses', async () => {
    const result = { n: 1, chunk_id: 'a', speaker: 'Jane Doe', party: 'Liberal', date: '2023-05-01', heading: 'H',
      text: 'full', snippet: 'a <mark>carbon</mark> tax', source_url: 'https://example.test/1', domains: [] }
    const searchFn = vi.fn()
      .mockResolvedValueOnce({ results: [result] })
      .mockResolvedValueOnce({ results: [] })
      .mockRejectedValueOnce(new Error('The search index is not available on the server yet.'))
    setup({ searchFn })
    await userEvent.click(screen.getByRole('radio', { name: 'Search' }))
    await userEvent.type(screen.getByRole('searchbox'), 'carbon')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByText('1 results')).toBeInTheDocument()
    expect(document.querySelector('mark')).toHaveTextContent('carbon')
    expect(searchFn.mock.calls[0][0]).toEqual({ query: 'carbon', top_k: 15 })

    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText(/No speeches matched your search/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('search index is not available')
  })

  it('still works when the filter options cannot be loaded', async () => {
    setup({ fetchFilters: vi.fn().mockRejectedValue(new Error('down')) })
    expect(await screen.findByLabelText('Party')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'All parties' })).toBeInTheDocument()
  })

  it('sends the bill filter in its canonical form, to the answer and to the chart', async () => {
    const streamFn = streamOf([{ event: 'done', data: { cited: [] } }])
    setup({ streamFn })
    await userEvent.type(await screen.findByLabelText('Bill'), 'c21')
    await userEvent.type(screen.getByRole('searchbox'), 'handgun freeze')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await waitFor(() => expect(streamFn).toHaveBeenCalled())
    expect(streamFn.mock.calls[0][0]).toEqual({ query: 'handgun freeze', bill: 'C-21' })
    expect(JSON.parse(screen.getByTestId('trend').textContent).filters).toEqual({ bill: 'C-21' })
  })

  it('refuses to search while the bill number is invalid and says why', async () => {
    const streamFn = streamOf([])
    setup({ streamFn })
    await userEvent.type(await screen.findByLabelText('Bill'), 'carbon')
    await userEvent.type(screen.getByRole('searchbox'), 'handgun freeze')
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
    expect(screen.getByText(/Fix the bill number in the filters/)).toBeInTheDocument()
    await userEvent.keyboard('{Enter}')
    expect(streamFn).not.toHaveBeenCalled()
    // correcting it re-enables the search
    await userEvent.clear(screen.getByLabelText('Bill'))
    expect(screen.getByRole('button', { name: 'Ask' })).toBeEnabled()
  })

  it('shows a "writing" state between the sources arriving and the first words', async () => {
    let release
    const gate = new Promise((r) => (release = r))
    const streamFn = vi.fn(async function* () {
      yield { event: 'sources', data: { sources: SOURCES } }
      await gate
      yield { event: 'token', data: { text: 'Done [1].' } }
      yield { event: 'done', data: { cited: [1] } }
    })
    setup({ streamFn })
    await userEvent.type(screen.getByRole('searchbox'), 'carbon pricing')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByText(/Reading them and writing an answer/)).toBeInTheDocument()
    expect(screen.getByText(/Found 2 relevant speeches/)).toBeInTheDocument()
    release()
    expect(await screen.findByText(/Done/)).toBeInTheDocument()
    expect(screen.queryByText(/Reading them and writing an answer/)).not.toBeInTheDocument()
  })

  it('renders even when the server sends only some of the filter options', async () => {
    setup({ fetchFilters: vi.fn().mockResolvedValue({ parties: ['Liberal'] }) })
    expect(await screen.findByRole('option', { name: 'Liberal' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
  })

  it('answers an unrelated question with the out-of-scope card and clickable alternatives', async () => {
    const streamFn = vi.fn(async function* (body) {
      if (body.query === 'What have MPs said about epilepsy?') {
        yield { event: 'sources', data: { sources: SOURCES } }
        yield { event: 'token', data: { text: 'Gill marked Epilepsy Day [1].' } }
        yield { event: 'done', data: { cited: [1], out_of_scope: false, suggestions: [] } }
        return
      }
      yield { event: 'sources', data: { sources: [] } }
      yield { event: 'token', data: { text: 'I could not find anything in the House of Commons debates related to that.' } }
      yield {
        event: 'done',
        data: {
          cited: [],
          out_of_scope: true,
          suggestions: ['What have MPs said about epilepsy?', 'What was said about bail reform?'],
        },
      }
    })
    setup({ streamFn })
    await userEvent.type(screen.getByRole('searchbox'), 'What is epilepsy?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    const card = await screen.findByRole('region', { name: 'Outside the record' })
    expect(within(card).getByText(/could not find anything in the House of Commons debates/)).toBeInTheDocument()
    expect(screen.queryByText(/No speeches matched your question/)).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Sources' })).not.toBeInTheDocument()

    // picking a suggestion runs it straight away and puts it in the search box
    await userEvent.click(within(card).getByRole('button', { name: 'What have MPs said about epilepsy?' }))
    expect(await screen.findByText(/Gill marked Epilepsy Day/)).toBeInTheDocument()
    expect(streamFn.mock.calls.at(-1)[0]).toEqual({ query: 'What have MPs said about epilepsy?' })
    expect(screen.getByRole('searchbox')).toHaveValue('What have MPs said about epilepsy?')
    expect(screen.queryByRole('region', { name: 'Outside the record' })).not.toBeInTheDocument()
  })

  it('shows no trend chart for a refused question, but does for a normal one', async () => {
    const refused = [
      { event: 'sources', data: { sources: [] } },
      { event: 'token', data: { text: 'Nothing related.' } },
      { event: 'done', data: { cited: [], out_of_scope: true, suggestions: [] } },
    ]
    const { unmount } = render(<App fetchFilters={vi.fn().mockResolvedValue(OPTIONS)} streamFn={streamOf(refused)} />)
    await userEvent.type(screen.getByRole('searchbox'), 'bake bread')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('region', { name: 'Outside the record' })
    expect(screen.queryByTestId('trend')).not.toBeInTheDocument()
    unmount()

    const normal = [
      { event: 'sources', data: { sources: SOURCES } },
      { event: 'token', data: { text: 'Answer [1].' } },
      { event: 'done', data: { cited: [1], out_of_scope: false, suggestions: [] } },
    ]
    render(<App fetchFilters={vi.fn().mockResolvedValue(OPTIONS)} streamFn={streamOf(normal)} />)
    await userEvent.type(screen.getByRole('searchbox'), 'carbon pricing')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByTestId('trend')).toBeInTheDocument()
  })

  it('offers a rewrite under a normal answer to a definition-style question', async () => {
    setup({
      streamFn: streamOf([
        { event: 'sources', data: { sources: SOURCES } },
        { event: 'token', data: { text: 'I only report debates. Gill said it is widespread [1].' } },
        { event: 'done', data: { cited: [1], out_of_scope: false, suggestions: ['What have MPs said about epilepsy?'] } },
      ]),
    })
    await userEvent.type(screen.getByRole('searchbox'), 'What is epilepsy?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    expect(await screen.findByText('You could also ask')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'What have MPs said about epilepsy?' })).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Sources' })).toBeInTheDocument() // the answer and sources stay
  })

  it('does not flash the "writing an answer" message when there is nothing to read', async () => {
    let release
    const gate = new Promise((r) => (release = r))
    const streamFn = vi.fn(async function* () {
      yield { event: 'sources', data: { sources: [] } }
      await gate
      yield { event: 'token', data: { text: 'Nothing related.' } }
      yield { event: 'done', data: { cited: [], out_of_scope: true, suggestions: [] } }
    })
    setup({ streamFn })
    await userEvent.type(screen.getByRole('searchbox'), 'bake bread')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await waitFor(() => expect(streamFn).toHaveBeenCalled())
    expect(screen.queryByText(/Reading them and writing an answer/)).not.toBeInTheDocument()
    release()
    expect(await screen.findByRole('region', { name: 'Outside the record' })).toBeInTheDocument()
  })
})

