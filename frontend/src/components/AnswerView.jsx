import { Fragment } from 'react'

// Citations are [1]; some models write full-width brackets \u30101\u3011, so both are accepted.
const TOKEN = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|[[\u3010]\d+[\]\u3011])/g

/** Inline text: **bold**, *italic* and [n] citation chips. Everything else is plain text (React escapes it). */
function Inline({ text, sourceCount, sources, onCite }) {
  const parts = text.split(TOKEN)
  const nodes = []
  for (let i = 0; i < parts.length; i++) {
    let part = parts[i]
    if (!part) continue
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      nodes.push(<strong key={i}>{part.slice(2, -2)}</strong>)
      continue
    }
    if (part.length > 2 && part.startsWith('*') && part.endsWith('*')) {
      nodes.push(<em key={i}>{part.slice(1, -1)}</em>)
      continue
    }
    const m = /^[[\u3010](\d+)[\]\u3011]$/.exec(part)
    if (m) {
      const n = Number(m[1])
      if (n >= 1 && n <= sourceCount) {
        const s = sources[n - 1]
        const label = s ? `Source ${n}: ${s.speaker ?? 'unknown speaker'}, ${s.date}` : `Source ${n}`
        const chip = (
          <button
            key={`chip-${i}`}
            type="button"
            onClick={() => onCite(n)}
            aria-label={label}
            title={label}
            className="mx-0.5 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded-full bg-brand px-1.5 align-middle font-sans text-[11px] font-semibold leading-none text-brandink transition hover:-translate-y-0.5 hover:bg-brandhover hover:shadow"
          >
            {n}
          </button>
        )
        // Keep punctuation that follows a chip on the same line as the chip.
        const next = parts[i + 1]
        const glue = typeof next === 'string' ? /^[.,;:!?)]+/.exec(next)?.[0] : null
        if (glue) {
          parts[i + 1] = next.slice(glue.length)
          nodes.push(
            <span key={i} className="whitespace-nowrap">
              {chip}
              {glue}
            </span>,
          )
        } else {
          nodes.push(chip)
        }
        continue
      }
    }
    nodes.push(<Fragment key={i}>{part}</Fragment>) // includes numbers that are not real sources
  }
  return nodes
}

// Models sometimes use narrow or no-break spaces (U+202F, U+00A0, thin spaces) inside names and numbers,
// which render as cramped gaps ("MarioBeaulieu"). Show them all as ordinary spaces.
const ODD_SPACES = /[\u00a0\u2007\u2009\u200a\u202f]/g

/** Split the answer into paragraphs and (possibly nested) bullet lists. */
function toBlocks(text) {
  const blocks = []
  for (const raw of text.replace(ODD_SPACES, ' ').split('\n')) {
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
    <div aria-live="polite" className="space-y-4 font-reading text-[1.06rem] leading-8 text-ink">
      {blocks.map((b, i) =>
        b.type === 'p' ? (
          <p key={i}>{inline(b.text)}</p>
        ) : (
          <ul key={i} className="list-disc space-y-3 pl-5 marker:text-gold">
            {b.items.map((it, j) => (
              <li key={j} className={it.depth ? 'ml-5 list-[circle]' : ''}>
                {inline(it.text)}
              </li>
            ))}
          </ul>
        ),
      )}
      {status === 'streaming' && (
        <span className="blink inline-block h-5 w-1.5 rounded-sm bg-brand align-middle" aria-hidden="true" />
      )}

      {status === 'done' && unverifiedQuotes.length > 0 && (
        <div
          role="note"
          className="rounded-xl border border-gold/40 bg-warntint p-4 font-sans text-sm leading-6 text-warnink"
        >
          <p className="font-medium">Check these quotes against the source</p>
          <p className="mt-1">
            The assistant put these words in quotation marks, but they do not appear exactly as written in
            the excerpt it cited. They may be paraphrased or slightly altered.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 marker:text-gold">
            {unverifiedQuotes.map((q, i) => (
              <li key={i}>
                “{q.quote}”{' '}
                {q.cited.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => onCite(n)}
                    className="mx-0.5 rounded-full bg-gold px-1.5 text-[11px] font-semibold text-white transition hover:brightness-110"
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
        <p role="note" className="font-sans text-sm text-warnink">
          The answer mentioned source numbers that do not exist ({invalidCitations.join(', ')}). Ignore those.
        </p>
      )}
    </div>
  )
}
