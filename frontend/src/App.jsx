import { useCallback, useEffect, useRef, useState } from 'react'
import { buildBody, cleanFilters, getFilters, search as apiSearch } from './api/client'
import About from './components/About'
import AnswerView from './components/AnswerView'
import CitationCard from './components/CitationCard'
import FilterPanel from './components/FilterPanel'
import ResultsList from './components/ResultsList'
import SearchBar from './components/SearchBar'
import TrendChart from './components/TrendChart'
import { useStreamedAnswer } from './hooks/useStreamedAnswer'
import { EMPTY_FILTERS } from './lib/filters'

const EXAMPLES = [
  'What did parties say about the carbon tax?',
  'How did MPs debate the Emergencies Act?',
  'What sanctions has Canada debated against Russia?',
  'What was said about bail reform?',
]

function Notice({ tone = 'info', children, role }) {
  const tones = {
    info: 'border-neutral-300 bg-neutral-50 text-neutral-800 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200',
    error: 'border-red-300 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200',
  }
  return (
    <div role={role} className={`rounded-lg border p-4 text-sm ${tones[tone]}`}>
      {children}
    </div>
  )
}

export default function App({ streamFn, searchFn = apiSearch, fetchFilters = getFilters }) {
  const [mode, setMode] = useState('ask')
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [options, setOptions] = useState(null)
  const [submitted, setSubmitted] = useState(null) // what the visible results and chart were run with

  const answer = useStreamedAnswer(streamFn)
  const [found, setFound] = useState({ status: 'idle', results: [], error: null })
  const searchCtl = useRef(null)

  // Filters are always open on desktop and collapsed on phones, so the search box stays in view.
  const [filtersOpen, setFiltersOpen] = useState(
    () => typeof window !== 'undefined' && !!window.matchMedia?.('(min-width: 1024px)').matches,
  )
  const activeFilters = Object.keys(cleanFilters(filters)).length

  const [expanded, setExpanded] = useState(() => new Set())
  const [highlight, setHighlight] = useState(null)

  useEffect(() => {
    fetchFilters().then(setOptions).catch(() => setOptions(null)) // filters still work, without the lists
  }, [fetchFilters])

  const submit = useCallback(() => {
    const q = query.trim()
    const body = buildBody(q, filters)
    setSubmitted({ query: q, mode, filters: { ...filters } })
    setExpanded(new Set())
    setHighlight(null)
    if (mode === 'ask') {
      searchCtl.current?.abort()
      setFound({ status: 'idle', results: [], error: null })
      answer.ask(body)
    } else {
      answer.reset()
      searchCtl.current?.abort()
      const ctl = new AbortController()
      searchCtl.current = ctl
      setFound({ status: 'loading', results: [], error: null })
      searchFn({ ...body, top_k: 15 }, { signal: ctl.signal })
        .then((d) => setFound({ status: 'done', results: d.results, error: null }))
        .catch((e) => {
          if (e?.name !== 'AbortError') setFound({ status: 'error', results: [], error: e.message })
        })
    }
  }, [query, filters, mode, answer, searchFn])

  const openCitation = useCallback((n) => {
    setExpanded((s) => new Set(s).add(n))
    setHighlight(n)
    requestAnimationFrame(() =>
      document.getElementById(`citation-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }),
    )
  }, [])

  const toggle = (n) =>
    setExpanded((s) => {
      const next = new Set(s)
      if (next.has(n)) next.delete(n)
      else next.add(n)
      return next
    })

  const askBusy = answer.status === 'loading' || answer.status === 'streaming'
  const busy = askBusy || found.status === 'loading'
  const showAsk = submitted?.mode === 'ask' && answer.status !== 'idle'
  const showSearch = submitted?.mode === 'search' && found.status !== 'idle'

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
      <header className="py-6">
        <h1 className="text-2xl font-bold tracking-tight">
          <span className="text-red-700 dark:text-red-500">Maple</span>Minutes
        </h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Ask questions about debates in the Canadian House of Commons, with every answer linked to the official record.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[17rem_1fr]">
        <aside className="lg:sticky lg:top-4 lg:self-start">
          <details
            open={filtersOpen}
            onToggle={(e) => setFiltersOpen(e.currentTarget.open)}
            className="rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900 lg:[&>summary]:hidden">
            <summary className="cursor-pointer text-sm font-semibold lg:hidden">
              Filters{activeFilters > 0 && ` (${activeFilters} active)`}
            </summary>
            <div className="mt-3 lg:mt-0">
              <FilterPanel options={options} value={filters} onChange={setFilters} />
              <p className="mt-3 text-xs text-neutral-500">Filters apply the next time you search.</p>
            </div>
          </details>
        </aside>

        <main className="min-w-0 space-y-6">
          <SearchBar
            value={query}
            onChange={setQuery}
            mode={mode}
            onModeChange={setMode}
            onSubmit={submit}
            busy={busy}
            onStop={answer.cancel}
          />

          {!submitted && (
            <div>
              <p className="mb-2 text-sm text-neutral-600 dark:text-neutral-400">Try one of these:</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    type="button"
                    onClick={() => setQuery(ex)}
                    className="rounded-full border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-200 dark:border-neutral-700 dark:hover:bg-neutral-800"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {showAsk && (
            <section aria-label="Answer" className="space-y-4">
              {answer.status === 'loading' && (
                <Notice role="status">
                  Searching the debates… If the server was idle, the first request can take 30 to 60 seconds.
                </Notice>
              )}
              {answer.text && (
                <div className="rounded-xl border border-neutral-200 bg-white p-5 dark:border-neutral-800 dark:bg-neutral-900">
                  <AnswerView
                    text={answer.text}
                    sources={answer.sources}
                    status={answer.status}
                    invalidCitations={answer.invalidCitations}
                    unverifiedQuotes={answer.unverifiedQuotes}
                    onCite={openCitation}
                  />
                </div>
              )}
              {answer.status === 'error' && (
                <Notice tone="error" role="alert">
                  {answer.error}
                  {answer.text && ' The answer above is incomplete.'}
                </Notice>
              )}
              {answer.status === 'done' && answer.sources.length === 0 && (
                <Notice>No speeches matched your question and filters. Try broader words or fewer filters.</Notice>
              )}
              {answer.sources.length > 0 && (
                <div>
                  <h2 className="mb-2 text-sm font-semibold">Sources ({answer.sources.length})</h2>
                  <ol className="space-y-2" aria-label="Sources">
                    {answer.sources.map((s) => (
                      <CitationCard
                        key={s.chunk_id}
                        source={s}
                        expanded={expanded.has(s.n)}
                        onToggle={toggle}
                        highlighted={highlight === s.n}
                      />
                    ))}
                  </ol>
                </div>
              )}
            </section>
          )}

          {showSearch && (
            <section aria-label="Search results" className="space-y-3">
              {found.status === 'loading' && (
                <Notice role="status">Searching… If the server was idle, the first request can take 30 to 60 seconds.</Notice>
              )}
              {found.status === 'error' && (
                <Notice tone="error" role="alert">
                  {found.error}
                </Notice>
              )}
              {found.status === 'done' && found.results.length === 0 && (
                <Notice>No speeches matched your search and filters. Try broader words or fewer filters.</Notice>
              )}
              {found.results.length > 0 && (
                <>
                  <h2 className="text-sm font-semibold">{found.results.length} results</h2>
                  <ResultsList results={found.results} />
                </>
              )}
            </section>
          )}

          {submitted && <TrendChart query={submitted.query} filters={cleanFilters(submitted.filters)} />}

          <About />
        </main>
      </div>
    </div>
  )
}
