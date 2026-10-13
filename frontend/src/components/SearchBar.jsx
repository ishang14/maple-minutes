const MODES = [
  { id: 'ask', label: 'Ask', hint: 'A cited answer written from the debates' },
  { id: 'search', label: 'Search', hint: 'A ranked list of matching speeches' },
]

export default function SearchBar({ value, onChange, mode, onModeChange, onSubmit, busy, onStop }) {
  const tooShort = value.trim().length < 2
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!tooShort && !busy) onSubmit()
      }}
      className="space-y-3"
      role="search"
    >
      <div role="radiogroup" aria-label="Mode" className="inline-flex rounded-lg border border-neutral-300 p-0.5 dark:border-neutral-700">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={mode === m.id}
            title={m.hint}
            onClick={() => onModeChange(m.id)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium ${
              mode === m.id
                ? 'bg-red-700 text-white'
                : 'text-neutral-700 hover:bg-neutral-200 dark:text-neutral-300 dark:hover:bg-neutral-800'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        <label htmlFor="query" className="sr-only">
          {mode === 'ask' ? 'Your question' : 'Search terms'}
        </label>
        <input
          id="query"
          type="search"
          value={value}
          maxLength={500}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            mode === 'ask'
              ? 'Ask a question, e.g. What did parties say about the Emergencies Act?'
              : 'Search the debates, e.g. carbon tax rebate'
          }
          className="min-w-0 flex-1 rounded-lg border border-neutral-300 bg-white px-4 py-2.5 text-base outline-none focus:border-red-600 focus:ring-2 focus:ring-red-600/30 dark:border-neutral-700 dark:bg-neutral-900"
        />
        {busy && mode === 'ask' ? (
          <button
            type="button"
            onClick={onStop}
            className="rounded-lg border border-neutral-400 px-5 py-2.5 text-sm font-semibold hover:bg-neutral-200 dark:hover:bg-neutral-800"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={tooShort || busy}
            className="rounded-lg bg-red-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mode === 'ask' ? 'Ask' : 'Search'}
          </button>
        )}
      </div>
    </form>
  )
}
