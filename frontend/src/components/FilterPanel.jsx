import { useEffect, useId, useRef, useState } from 'react'
import { getSpeakers } from '../api/client'
import { useDebounced } from '../hooks/useDebounced'
import { EMPTY_FILTERS } from '../lib/filters'
import { DOMAIN_LABELS } from '../lib/parties'

const inputCls =
  'w-full rounded-md border border-neutral-300 bg-white px-2.5 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900'

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
          className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-md border border-neutral-300 bg-white py-1 text-sm shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
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
              className={`cursor-pointer px-2.5 py-1.5 ${i === active ? 'bg-red-100 dark:bg-red-950' : ''}`}
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

  return (
    <fieldset className="space-y-4">
      <legend className="sr-only">Filters</legend>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label htmlFor="date_from" className="mb-1 block text-xs font-medium">
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
          <label htmlFor="date_to" className="mb-1 block text-xs font-medium">
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
        <label htmlFor="party" className="mb-1 block text-xs font-medium">
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
        <label htmlFor="speaker" className="mb-1 block text-xs font-medium">
          Member of Parliament
        </label>
        <SpeakerField key={resetCount} value={value.speaker} onPick={(speaker) => set({ speaker })} fetchSpeakers={fetchSpeakers} />
      </div>

      <div>
        <label htmlFor="parliament" className="mb-1 block text-xs font-medium">
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

      <div role="group" aria-labelledby="topics-label">
        <p id="topics-label" className="mb-1 text-xs font-medium">
          Topics
        </p>
        <div className="space-y-1.5">
          {Object.entries(DOMAIN_LABELS).map(([id, label]) => (
            <label key={id} className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={value.domains.includes(id)}
                onChange={() => toggleDomain(id)}
                className="mt-0.5 accent-red-700"
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
        className="text-sm font-medium text-red-700 underline underline-offset-2 disabled:no-underline disabled:opacity-40 dark:text-red-400"
      >
        Reset filters
      </button>
    </fieldset>
  )
}
