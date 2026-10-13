const MODES = [
  { id: 'ask', label: 'Ask', hint: 'A cited answer written from the debates' },
  { id: 'search', label: 'Search', hint: 'A ranked list of matching speeches' },
]

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4.5 4.5" strokeLinecap="round" />
    </svg>
  )
}

export default function SearchBar({ value, onChange, mode, onModeChange, onSubmit, busy, onStop, blockedReason }) {
  const tooShort = value.trim().length < 2
  const blocked = tooShort || Boolean(blockedReason)
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!blocked && !busy) onSubmit()
      }}
      className="space-y-4 rounded-2xl border border-line bg-surface p-4 shadow-card sm:p-5"
      role="search"
    >
      <div
        role="radiogroup"
        aria-label="Mode"
        className="inline-flex rounded-full bg-tint p-1 text-sm"
      >
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={mode === m.id}
            title={m.hint}
            onClick={() => onModeChange(m.id)}
            className={`rounded-full px-5 py-1.5 font-medium transition-all duration-200 ${
              mode === m.id
                ? 'bg-brand text-brandink shadow-sm'
                : 'text-tintink hover:bg-surface/60'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="query" className="sr-only">
          {mode === 'ask' ? 'Your question' : 'Search terms'}
        </label>
        <div className="relative min-w-0 flex-1">
          <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-faint">
            <SearchIcon />
          </span>
          <input
            id="query"
            type="search"
            value={value}
            maxLength={500}
            onChange={(e) => onChange(e.target.value)}
            placeholder={
              mode === 'ask'
                ? 'What did parties say about the Emergencies Act?'
                : 'Search the debates, e.g. carbon tax rebate'
            }
            className="h-12 w-full rounded-xl border border-line bg-surface2 pl-12 pr-4 text-base text-ink outline-none transition placeholder:text-faint focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/15"
          />
        </div>
        {busy && mode === 'ask' ? (
          <button
            type="button"
            onClick={onStop}
            className="h-12 rounded-xl border border-linestrong px-6 text-sm font-semibold transition hover:bg-tint active:scale-[0.98]"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={blocked || busy}
            title={blockedReason || undefined}
            className="h-12 rounded-xl bg-brand px-7 text-sm font-semibold text-brandink shadow-sm transition hover:bg-brandhover hover:shadow-md active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none"
          >
            {mode === 'ask' ? 'Ask' : 'Search'}
          </button>
        )}
      </div>
      {blockedReason && (
        <p role="alert" className="text-sm text-danger">
          {blockedReason}
        </p>
      )}
    </form>
  )
}
