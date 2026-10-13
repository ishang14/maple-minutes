import { useState } from 'react'
import { DOMAIN_LABELS } from '../lib/parties'

function Result({ r, index }) {
  const [open, setOpen] = useState(false)
  const who = [r.speaker, r.party && `(${r.party})`].filter(Boolean).join(' ')
  return (
    <li
      className="fade-up rounded-xl border border-line bg-surface p-5 shadow-card transition-all duration-200 hover:-translate-y-0.5 hover:border-linestrong hover:shadow-lift"
      style={{ '--delay': `${Math.min(index, 8) * 45}ms` }}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-tint px-1.5 text-xs font-semibold text-tintink">
          {r.n}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-ink">{who || 'Unknown speaker'}</p>
          <p className="text-xs text-muted">
            {[r.date, r.heading, r.bill].filter(Boolean).join(' · ')}
          </p>
          {open ? (
            <p className="mt-3 whitespace-pre-line font-reading text-[0.98rem] leading-7">{r.text}</p>
          ) : (
            // The server HTML-escapes the speech text and only adds <mark> tags, so this is safe.
            <p className="mt-3 font-reading text-[0.98rem] leading-7" dangerouslySetInnerHTML={{ __html: r.snippet }} />
          )}
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              className="font-medium text-brand underline decoration-brand/40 underline-offset-4 transition hover:decoration-brand"
            >
              {open ? 'Show less' : 'Read full speech'}
            </button>
            <a
              href={r.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-brand underline decoration-brand/40 underline-offset-4 transition hover:decoration-brand"
            >
              Official Hansard ↗
            </a>
            {r.domains?.length > 0 && (
              <span className="text-faint">{r.domains.map((d) => DOMAIN_LABELS[d] ?? d).join(' · ')}</span>
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
      {results.map((r, i) => (
        <Result key={r.chunk_id} r={r} index={i} />
      ))}
    </ol>
  )
}
