import { DOMAIN_LABELS } from '../lib/parties'

/** One retrieved speech: a collapsed summary line that expands to the excerpt and a link. */
export default function CitationCard({ source, expanded, onToggle, highlighted = false }) {
  const { n, speaker, party, riding, role, date, heading, bill, domains = [], text, source_url } = source
  const who = [speaker, party && `(${party})`].filter(Boolean).join(' ')
  const panelId = `citation-panel-${n}`
  return (
    <li
      id={`citation-${n}`}
      className={`overflow-hidden rounded-xl border bg-surface shadow-card transition-all duration-300 ${
        highlighted ? 'border-brand ring-2 ring-brand/30' : 'border-line hover:border-linestrong'
      }`}
    >
      <button
        type="button"
        onClick={() => onToggle(n)}
        aria-expanded={expanded}
        aria-controls={panelId}
        className="flex w-full items-start gap-3 p-3.5 text-left transition-colors hover:bg-surface2"
      >
        <span className="mt-0.5 inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-tint px-1.5 text-xs font-semibold text-tintink">
          {n}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-ink">{who || 'Unknown speaker'}</span>
          <span className="block truncate text-xs text-muted">
            {[date, heading].filter(Boolean).join(' · ')}
          </span>
        </span>
        <span aria-hidden="true" className="text-lg leading-none text-faint">
          {expanded ? '−' : '+'}
        </span>
      </button>

      {expanded && (
        <div id={panelId} className="fade-down border-t border-line bg-surface2 p-4 text-sm">
          <p className="whitespace-pre-line font-reading text-[0.98rem] leading-7 text-ink">{text}</p>
          <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
            {riding && (
              <div>
                <dt className="inline font-medium">Riding: </dt>
                <dd className="inline">{riding}</dd>
              </div>
            )}
            {role && (
              <div>
                <dt className="inline font-medium">Role: </dt>
                <dd className="inline">{role}</dd>
              </div>
            )}
            {bill && (
              <div>
                <dt className="inline font-medium">Bill: </dt>
                <dd className="inline">{bill}</dd>
              </div>
            )}
            {domains.length > 0 && (
              <div>
                <dt className="inline font-medium">Topics: </dt>
                <dd className="inline">{domains.map((d) => DOMAIN_LABELS[d] ?? d).join(', ')}</dd>
              </div>
            )}
          </dl>
          <a
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-block text-sm font-medium text-brand underline decoration-brand/40 underline-offset-4 transition hover:decoration-brand"
          >
            Open in the official Hansard ↗
          </a>
        </div>
      )}
    </li>
  )
}
