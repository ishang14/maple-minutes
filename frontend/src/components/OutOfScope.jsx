import Suggestions from './Suggestions'

/** Shown when the question has no relationship to anything in the debates. */
export default function OutOfScope({ message, suggestions, onPick }) {
  return (
    <section
      aria-label="Outside the record"
      className="fade-up space-y-6 rounded-2xl border border-gold/40 bg-surface p-6 shadow-lift sm:p-8"
    >
      <div className="flex gap-4">
        <span
          className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-goldtint text-gold"
          aria-hidden="true"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="12" cy="12" r="9" />
            <path d="m15.5 8.5-2 5-5 2 2-5z" strokeLinejoin="round" />
          </svg>
        </span>
        <div>
          <h2 className="font-serif text-xl font-medium tracking-tight text-ink">That is outside the record</h2>
          <p className="mt-2 font-reading text-[1.02rem] leading-7 text-muted">{message}</p>
        </div>
      </div>
      <Suggestions items={suggestions} onPick={onPick} label="Try asking" />
    </section>
  )
}
