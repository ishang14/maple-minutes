import { useEffect, useId, useRef, useState } from 'react'
import { getSpeakers } from '../api/client'
import { useDebounced } from '../hooks/useDebounced'
import { EMPTY_FILTERS, normalizeBill } from '../lib/filters'
import { DOMAIN_LABELS } from '../lib/parties'

const inputCls =
  'w-full rounded-lg border border-line bg-surface2 px-3 py-2 text-sm text-ink outline-none transition placeholder:text-faint focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/15'
const labelCls = 'mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted'

/** MP name autocomplete: suggestions come from GET /filters/speakers, picking one sets the filter. */
function SpeakerField({ value, onPick, fetchSpeakers = getSpeakers }) {
  const [text, setText] = useState(value)
  const [options, setOptions] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const debounced = useDebounced(text, 250)
  const listId = useId()
  const picked = useRef(value)

  useEffect(() => {
    const q = debounced.trim()
    if (q.length < 2 || q === picked.current) {
      setOptions([])
      return
    }
    const ctl = new AbortController()
    fetchSpeakers(q, { signal: ctl.signal })
      .then((list) => {
        setOptions(list)
        setActive(-1)
      })
      .catch(() => setOptions([]))
    return () => ctl.abort()
  }, [debounced, fetchSpeakers])

  const choose = (name) => {
    picked.current = name
    setText(name)
    setOpen(false)
    onPick(name)
  }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((a) => Math.min(a + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter' && open && active >= 0) {
      e.preventDefault()
      choose(options[active])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative">
      <input
        id="speaker"
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        autoComplete="off"
        value={text}
        placeholder="Start typing a name"
        className={inputCls}
        onChange={(e) => {
          setText(e.target.value)
          setOpen(true)
          if (value && e.target.value !== value) {
            picked.current = ''
            onPick('') // editing the name drops the previous pick
          }
        }}
        onKeyDown={onKeyDown}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
      />
      {open && options.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="fade-down absolute z-20 mt-1.5 max-h-56 w-full overflow-auto rounded-xl border border-line bg-surface py-1.5 text-sm shadow-lift"
        >
          {options.map((name, i) => (
            <li
              key={name}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault()
                choose(name)
              }}
              className={`cursor-pointer px-3 py-1.5 transition-colors ${i === active ? 'bg-tint text-tintink' : 'hover:bg-surface2'}`}
            >
              {name}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function FilterPanel({ options, value, onChange, fetchSpeakers }) {
  const [resetCount, setResetCount] = useState(0) // remounts the name box so Reset clears its text
  const set = (patch) => onChange({ ...value, ...patch })
  const toggleDomain = (id) =>
    set({ domains: value.domains.includes(id) ? value.domains.filter((d) => d !== id) : [...value.domains, id] })
  const active = JSON.stringify(value) !== JSON.stringify(EMPTY_FILTERS)
  const billInvalid = normalizeBill(value.bill) === null

  return (
    <fieldset className="space-y-5">
      <legend className="sr-only">Filters</legend>

      <div className="grid grid-cols-1 gap-3">
        <div>
          <label htmlFor="date_from" className={labelCls}>
            From
          </label>
          <input
            id="date_from"
            type="date"
            value={value.date_from}
            min={options?.date_min}
            max={value.date_to || options?.date_max}
            onChange={(e) => set({ date_from: e.target.value })}
            className={inputCls}
          />
        </div>
        <div>
          <label htmlFor="date_to" className={labelCls}>
            To
          </label>
          <input
            id="date_to"
            type="date"
            value={value.date_to}
            min={value.date_from || options?.date_min}
            max={options?.date_max}
            onChange={(e) => set({ date_to: e.target.value })}
            className={inputCls}
          />
        </div>
      </div>

      <div>
        <label htmlFor="party" className={labelCls}>
          Party
        </label>
        <select id="party" value={value.party} onChange={(e) => set({ party: e.target.value })} className={inputCls}>
          <option value="">All parties</option>
          {(options?.parties ?? []).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="speaker" className={labelCls}>
          Member of Parliament
        </label>
        <SpeakerField key={resetCount} value={value.speaker} onPick={(speaker) => set({ speaker })} fetchSpeakers={fetchSpeakers} />
      </div>

      <div>
        <label htmlFor="parliament" className={labelCls}>
          Parliament
        </label>
        <select
          id="parliament"
          value={value.parliament}
          onChange={(e) => set({ parliament: e.target.value })}
          className={inputCls}
        >
          <option value="">All (43rd to 45th)</option>
          {(options?.parliaments ?? []).map((p) => (
            <option key={p} value={p}>
              {p}th Parliament
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="bill" className={labelCls}>
          Bill
        </label>
        <input
          id="bill"
          value={value.bill}
          list="bill-options"
          placeholder="e.g. C-21"
          autoComplete="off"
          aria-invalid={billInvalid}
          aria-describedby="bill-help"
          className={`${inputCls} ${billInvalid ? 'border-danger' : ''}`}
          onChange={(e) => set({ bill: e.target.value })}
          onBlur={() => {
            const canonical = normalizeBill(value.bill)
            if (canonical && canonical !== value.bill) set({ bill: canonical })
          }}
        />
        <datalist id="bill-options">
          {(options?.bills ?? []).map((b) => (
            <option key={b} value={b} />
          ))}
        </datalist>
        {billInvalid ? (
          <p id="bill-help" role="alert" className="mt-1.5 text-xs text-danger">
            Use a bill number such as C-21 or S-3.
          </p>
        ) : (
          <p id="bill-help" className="mt-1.5 text-xs text-faint">
            Bill numbers restart each Parliament, so pair this with the Parliament filter.
          </p>
        )}
      </div>

      <div role="group" aria-labelledby="topics-label">
        <p id="topics-label" className={labelCls}>
          Topics
        </p>
        <div className="space-y-1.5">
          {Object.entries(DOMAIN_LABELS).map(([id, label]) => (
            <label key={id} className="flex cursor-pointer items-start gap-2.5 text-sm text-ink">
              <input
                type="checkbox"
                checked={value.domains.includes(id)}
                onChange={() => toggleDomain(id)}
                className="mt-0.5 h-4 w-4 accent-brand"
              />
              <span>{options?.domains?.find((d) => d.id === id)?.label ?? label}</span>
            </label>
          ))}
        </div>
      </div>

      <button
        type="button"
        onClick={() => {
          setResetCount((c) => c + 1)
          onChange(EMPTY_FILTERS)
        }}
        disabled={!active}
        className="text-sm font-medium text-brand underline decoration-brand/40 underline-offset-4 transition hover:decoration-brand disabled:no-underline disabled:opacity-40"
      >
        Reset filters
      </button>
    </fieldset>
  )
}
