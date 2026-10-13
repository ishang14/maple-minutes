import { useState } from 'react'
import { DOMAIN_LABELS } from '../lib/parties'

function Result({ r }) {
  const [open, setOpen] = useState(false)
  const who = [r.speaker, r.party && `(${r.party})`].filter(Boolean).join(' ')
  return (
    <li className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-6 min-w-6 items-center justify-center rounded bg-neutral-200 px-1.5 text-xs font-semibold dark:bg-neutral-700">
          {r.n}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{who || 'Unknown speaker'}</p>
          <p className="text-xs text-neutral-600 dark:text-neutral-400">
            {[r.date, r.heading, r.bill].filter(Boolean).join(' · ')}
          </p>
          {open ? (
            <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">{r.text}</p>
          ) : (
            // The server HTML-escapes the speech text and only adds <mark> tags, so this is safe.
            <p className="mt-2 text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: r.snippet }} />
          )}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              className="font-medium text-red-700 underline underline-offset-2 dark:text-red-400"
            >
              {open ? 'Show less' : 'Read full speech'}
            </button>
            <a
              href={r.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-red-700 underline underline-offset-2 dark:text-red-400"
            >
              Official Hansard ↗
            </a>
            {r.domains?.length > 0 && (
              <span className="text-neutral-500">{r.domains.map((d) => DOMAIN_LABELS[d] ?? d).join(' · ')}</span>
            )}
          </div>
        </div>
      </div>
    </li>
  )
}

export default function ResultsList({ results }) {
  return (
    <ol className="space-y-3" aria-label="Search results">
      {results.map((r) => (
        <Result key={r.chunk_id} r={r} />
      ))}
    </ol>
  )
}
