import { useCallback, useEffect, useRef, useState } from 'react'
import { buildBody, cleanFilters, getFilters, search as apiSearch } from './api/client'
import About from './components/About'
import AnswerView from './components/AnswerView'
import CitationCard from './components/CitationCard'
import FilterPanel from './components/FilterPanel'
import Logo from './components/Logo'
import OutOfScope from './components/OutOfScope'
import ResultsList from './components/ResultsList'
import SearchBar from './components/SearchBar'
import Suggestions from './components/Suggestions'
import TrendChart from './components/TrendChart'
import { useStreamedAnswer } from './hooks/useStreamedAnswer'
import { EMPTY_FILTERS, normalizeBill } from './lib/filters'

const EXAMPLES = [
  'What did parties say about the carbon tax?',
  'How did MPs debate the Emergencies Act?',
  'What sanctions has Canada debated against Russia?',
  'What was said about bail reform?',
]

const ordinal = (n) => {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

const monthYear = (iso) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('en-CA', { month: 'short', year: 'numeric' })

function Notice({ tone = 'info', children, role }) {
  const tones = {
    info: 'border-line bg-surface text-ink',
    error: 'border-danger/30 bg-dangertint text-danger',
  }
  return (
    <div role={role} className={`fade-down rounded-xl border p-4 text-sm leading-6 shadow-card ${tones[tone]}`}>
      {children}
    </div>
  )
}

/** Shown while waiting for the first words: three pulsing dots, the message, and soft placeholder lines. */
function Thinking({ children }) {
  return (
    <div role="status" className="fade-down rounded-2xl border border-line bg-surface p-6 shadow-card">
      <p className="flex items-center gap-3 text-sm text-muted">
        <span className="flex gap-1" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="dot-pulse h-2 w-2 rounded-full bg-brand"
              style={{ animationDelay: `${i * 160}ms` }}
            />
          ))}
        </span>
        {children}
      </p>
      <div className="mt-5 space-y-3" aria-hidden="true">
        <div className="skeleton h-3.5 w-11/12" />
        <div className="skeleton h-3.5 w-full" />
        <div className="skeleton h-3.5 w-3/4" />
      </div>
    </div>
  )
}

function Hero({ options }) {
  // Each figure appears only when the server supplied it, so a partial response never breaks the page.
  const parl = options?.parliaments
  const stats = [
    options?.chunks != null && [options.chunks.toLocaleString('en'), 'speech excerpts'],
    options?.date_min && options?.date_max && [`${monthYear(options.date_min)} to ${monthYear(options.date_max)}`, 'of debates'],
    parl?.length > 0 && [`${ordinal(parl[0])}–${ordinal(parl.at(-1))}`, 'Parliaments'],
  ].filter(Boolean)
  return (
    <section className="fade-up mx-auto max-w-3xl pb-8 pt-10 text-center sm:pb-10 sm:pt-16">
      <p className="mx-auto inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3.5 py-1 text-xs font-medium uppercase tracking-[0.14em] text-muted shadow-card">
        <span className="h-1.5 w-1.5 rounded-full bg-gold" aria-hidden="true" />
        House of Commons · Hansard
      </p>
      <h1 className="mt-6 font-serif text-4xl font-medium leading-[1.08] tracking-tight text-ink sm:text-6xl">
        What did Parliament <span className="italic text-brand">actually</span> say?
      </h1>
      <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted sm:text-lg">
        Ask in plain language. Get an answer written from the official record, with every claim linked to the exact
        speech.
      </p>
      {stats.length > 0 && (
        <dl className="fade-up mt-8 grid grid-cols-3 gap-2 sm:flex sm:flex-wrap sm:justify-center sm:gap-x-10 sm:gap-y-4" style={{ '--delay': '120ms' }}>
          {stats.map(([value, label]) => (
            <div key={label}>
              <dt className="sr-only">{label}</dt>
              <dd className="font-serif text-base font-medium leading-tight text-ink sm:text-2xl">{value}</dd>
              <dd className="mt-1 text-[10px] uppercase tracking-wider text-faint sm:text-xs">{label}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
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
  const invalidBill = normalizeBill(filters.bill) === null

  const [expanded, setExpanded] = useState(() => new Set())
  const [highlight, setHighlight] = useState(null)

  useEffect(() => {
    fetchFilters().then(setOptions).catch(() => setOptions(null)) // filters still work, without the lists
  }, [fetchFilters])

  // `override` lets a suggestion chip run its own question without waiting for the input to update.
  const submit = useCallback((override) => {
    if (invalidBill) return
    const q = (typeof override === 'string' ? override : query).trim()
    const effective = { ...filters, bill: normalizeBill(filters.bill) } // "c21" -> "C-21"
    const askMode = typeof override === 'string' ? 'ask' : mode
    if (askMode !== mode) setMode(askMode)
    const body = buildBody(q, effective)
    setSubmitted({ query: q, mode: askMode, filters: effective })
    setExpanded(new Set())
    setHighlight(null)
    if (askMode === 'ask') {
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
  }, [query, filters, mode, answer, searchFn, invalidBill])

  const runSuggestion = useCallback(
    (q) => {
      setQuery(q)
      submit(q)
    },
    [submit],
  )

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
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <a href="/" className="flex items-center gap-2.5 text-ink" aria-label="MapleMinutes home">
            <span className="text-maple">
              <Logo className="h-6 w-6" />
            </span>
            <span className="font-serif text-xl font-medium tracking-tight">
              Maple<span className="text-brand">Minutes</span>
            </span>
          </a>
          <a
            href="#about"
            className="text-sm font-medium text-muted underline decoration-transparent underline-offset-4 transition hover:text-ink hover:decoration-current"
          >
            About and limitations
          </a>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        {!submitted && <Hero options={options} />}

        <div className={`grid gap-6 lg:grid-cols-[17.5rem_1fr] ${submitted ? 'pt-6' : ''}`}>
          <aside className="lg:sticky lg:top-20 lg:self-start">
            <details
              open={filtersOpen}
              onToggle={(e) => setFiltersOpen(e.currentTarget.open)}
              className="rounded-2xl border border-line bg-surface p-5 shadow-card lg:[&>summary]:hidden"
            >
              <summary className="cursor-pointer text-sm font-semibold text-ink lg:hidden">
                Filters{activeFilters > 0 && ` (${activeFilters} active)`}
              </summary>
              <div className="mt-4 lg:mt-0">
                <FilterPanel options={options} value={filters} onChange={setFilters} />
                <p className="mt-4 text-xs text-faint">Filters apply the next time you search.</p>
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
              blockedReason={invalidBill ? 'Fix the bill number in the filters (for example C-21) to search.' : ''}
            />

            {!submitted && (
              <div className="fade-up" style={{ '--delay': '200ms' }}>
                <p className="mb-3 text-xs font-medium uppercase tracking-wider text-faint">Try one of these</p>
                <div className="flex flex-wrap gap-2.5">
                  {EXAMPLES.map((ex) => (
                    <button
                      key={ex}
                      type="button"
                      onClick={() => setQuery(ex)}
                      className="rounded-full border border-line bg-surface px-4 py-2 text-left text-sm text-ink shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:border-brand hover:text-brand hover:shadow-lift active:translate-y-0"
                    >
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {showAsk && (
              <section aria-label="Answer" className="space-y-5">
                {answer.status === 'loading' && (
                  <Thinking>
                    Searching the debates… If the server was idle, the first request can take 30 to 60 seconds.
                  </Thinking>
                )}
                {answer.status === 'streaming' && !answer.text && answer.sources.length > 0 && (
                  <Thinking>Found {answer.sources.length} relevant speeches. Reading them and writing an answer…</Thinking>
                )}
                {answer.outOfScope && (
                  <OutOfScope message={answer.text} suggestions={answer.suggestions} onPick={runSuggestion} />
                )}
                {answer.text && !answer.outOfScope && (
                  <div className="fade-up rounded-2xl border border-line bg-surface p-6 shadow-lift sm:p-8">
                    <p className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-brand">
                      <span className="h-px w-6 bg-gold" aria-hidden="true" />
                      Answer
                    </p>
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
                {answer.status === 'done' && answer.sources.length === 0 && !answer.outOfScope && (
                  <Notice>No speeches matched your question and filters. Try broader words or fewer filters.</Notice>
                )}
                {answer.status === 'done' && !answer.outOfScope && (
                  <Suggestions items={answer.suggestions} onPick={runSuggestion} label="You could also ask" />
                )}
                {answer.sources.length > 0 && (
                  <div className="fade-up">
                    <h2 className="mb-3 font-serif text-xl font-medium tracking-tight">
                      Sources <span className="text-base text-faint">({answer.sources.length})</span>
                    </h2>
                    <ol className="space-y-2.5" aria-label="Sources">
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
              <section aria-label="Search results" className="space-y-4">
                {found.status === 'loading' && (
                  <Thinking>Searching… If the server was idle, the first request can take 30 to 60 seconds.</Thinking>
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
                    <h2 className="font-serif text-xl font-medium tracking-tight">{found.results.length} results</h2>
                    <ResultsList results={found.results} />
                  </>
                )}
              </section>
            )}

            {/* a refused question has no topic to chart */}
            {submitted && !answer.outOfScope && (
              <TrendChart query={submitted.query} filters={cleanFilters(submitted.filters)} />
            )}

            <About />
          </main>
        </div>
      </div>

      <footer className="border-t border-line/70 py-8 text-center text-xs text-faint">
        <span className="inline-flex items-center gap-2">
          <span className="text-maple">
            <Logo className="h-4 w-4" />
          </span>
          MapleMinutes · An independent project built on the House of Commons Hansard. Not an official publication.
        </span>
      </footer>
    </div>
  )
}
