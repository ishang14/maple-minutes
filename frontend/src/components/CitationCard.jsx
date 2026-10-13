import { DOMAIN_LABELS } from '../lib/parties'

/** One retrieved speech: a collapsed summary line that expands to the excerpt and a link. */
export default function CitationCard({ source, expanded, onToggle, highlighted = false }) {
  const { n, speaker, party, riding, role, date, heading, bill, domains = [], text, source_url } = source
  const who = [speaker, party && `(${party})`].filter(Boolean).join(' ')
  const panelId = `citation-panel-${n}`
  return (
    <li
      id={`citation-${n}`}
      className={`rounded-lg border bg-white dark:bg-neutral-900 transition-shadow ${
        highlighted
          ? 'border-red-500 ring-2 ring-red-500/30'
          : 'border-neutral-200 dark:border-neutral-800'
      }`}
    >
      <button
        type="button"
        onClick={() => onToggle(n)}
        aria-expanded={expanded}
        aria-controls={panelId}
        className="flex w-full items-start gap-3 p-3 text-left"
      >
        <span className="mt-0.5 inline-flex h-6 min-w-6 items-center justify-center rounded bg-red-700 px-1.5 text-xs font-semibold text-white">
          {n}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{who || 'Unknown speaker'}</span>
          <span className="block truncate text-xs text-neutral-600 dark:text-neutral-400">
            {[date, heading].filter(Boolean).join(' · ')}
          </span>
        </span>
        <span aria-hidden="true" className="text-neutral-500">
          {expanded ? '−' : '+'}
        </span>
      </button>

      {expanded && (
        <div id={panelId} className="border-t border-neutral-200 p-3 text-sm dark:border-neutral-800">
          <p className="whitespace-pre-line leading-relaxed">{text}</p>
          <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-neutral-600 dark:text-neutral-400">
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
            className="mt-3 inline-block text-sm font-medium text-red-700 underline underline-offset-2 hover:text-red-800 dark:text-red-400"
          >
            Open in the official Hansard ↗
          </a>
        </div>
      )}
    </li>
  )
}
