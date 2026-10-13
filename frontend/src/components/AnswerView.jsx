import { Fragment } from 'react'

const TOKEN = /(\*\*[^*]+\*\*|\[\d+\])/g

/** Inline text: **bold** and [n] citation chips. Everything else is plain text (React escapes it). */
function Inline({ text, sourceCount, sources, onCite }) {
  return text.split(TOKEN).map((part, i) => {
    if (!part) return null
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    const m = /^\[(\d+)\]$/.exec(part)
    if (m) {
      const n = Number(m[1])
      if (n >= 1 && n <= sourceCount) {
        const s = sources[n - 1]
        const label = s ? `Source ${n}: ${s.speaker ?? 'unknown speaker'}, ${s.date}` : `Source ${n}`
        return (
          <button
            key={i}
            type="button"
            onClick={() => onCite(n)}
            aria-label={label}
            title={label}
            className="mx-0.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded bg-red-700 px-1 align-middle text-[11px] font-semibold leading-none text-white hover:bg-red-800 focus:outline-2 focus:outline-offset-1 focus:outline-red-600"
          >
            {n}
          </button>
        )
      }
      return <Fragment key={i}>{part}</Fragment> // a number that is not a real source stays plain text
    }
    return <Fragment key={i}>{part}</Fragment>
  })
}

/** Split the answer into paragraphs and (possibly nested) bullet lists. */
function toBlocks(text) {
  const blocks = []
  for (const raw of text.split('\n')) {
    if (!raw.trim()) continue
    const bullet = /^(\s*)[-*•]\s+(.*)$/.exec(raw)
    if (bullet) {
      const depth = bullet[1].length >= 2 ? 1 : 0
      const last = blocks[blocks.length - 1]
      if (last?.type === 'list') last.items.push({ depth, text: bullet[2] })
      else blocks.push({ type: 'list', items: [{ depth, text: bullet[2] }] })
    } else {
      blocks.push({ type: 'p', text: raw.trim() })
    }
  }
  return blocks
}

export default function AnswerView({
  text,
  sources,
  status,
  invalidCitations = [],
  unverifiedQuotes = [],
  onCite,
}) {
  const blocks = toBlocks(text)
  const inline = (t) => <Inline text={t} sourceCount={sources.length} sources={sources} onCite={onCite} />
  return (
    <div aria-live="polite" className="space-y-3 leading-relaxed">
      {blocks.map((b, i) =>
        b.type === 'p' ? (
          <p key={i}>{inline(b.text)}</p>
        ) : (
          <ul key={i} className="list-disc space-y-1.5 pl-5">
            {b.items.map((it, j) => (
              <li key={j} className={it.depth ? 'ml-5 list-[circle]' : ''}>
                {inline(it.text)}
              </li>
            ))}
          </ul>
        ),
      )}
      {status === 'streaming' && (
        <span className="blink inline-block h-4 w-1.5 bg-neutral-500 align-middle" aria-hidden="true" />
      )}

      {status === 'done' && unverifiedQuotes.length > 0 && (
        <div
          role="note"
          className="rounded-md border border-amber-400 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
        >
          <p className="font-medium">Check these quotes against the source</p>
          <p className="mt-1">
            The assistant put these words in quotation marks, but they do not appear exactly as written in
            the excerpt it cited. They may be paraphrased or slightly altered.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {unverifiedQuotes.map((q, i) => (
              <li key={i}>
                “{q.quote}”{' '}
                {q.cited.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => onCite(n)}
                    className="mx-0.5 rounded bg-amber-700 px-1 text-[11px] font-semibold text-white"
                    aria-label={`Open source ${n}`}
                  >
                    {n}
                  </button>
                ))}
              </li>
            ))}
          </ul>
        </div>
      )}

      {status === 'done' && invalidCitations.length > 0 && (
        <p role="note" className="text-sm text-amber-800 dark:text-amber-300">
          The answer mentioned source numbers that do not exist ({invalidCitations.join(', ')}). Ignore those.
        </p>
      )}
    </div>
  )
}
