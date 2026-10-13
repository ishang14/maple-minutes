/** Clickable questions to try instead; choosing one runs it straight away. */
export default function Suggestions({ items, onPick, label = 'You could try' }) {
  if (!items?.length) return null
  return (
    <div className="fade-up">
      <p className="mb-2.5 text-xs font-medium uppercase tracking-wider text-faint">{label}</p>
      <div className="flex flex-wrap gap-2.5">
        {items.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onPick(q)}
            className="rounded-full border border-line bg-surface px-4 py-2 text-left text-sm text-ink shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:border-brand hover:text-brand hover:shadow-lift active:translate-y-0"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
