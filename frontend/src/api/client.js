// Thin client for the MapleMinutes backend. Every function takes an optional AbortSignal.

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const FRIENDLY = {
  503: 'The search index is not available on the server yet. Please try again shortly.',
  429: 'Too many requests. Please wait a moment and try again.',
}

async function errorFromResponse(res) {
  if (FRIENDLY[res.status]) return new ApiError(FRIENDLY[res.status], res.status)
  let detail = ''
  try {
    const body = await res.json()
    const d = body.detail
    detail = Array.isArray(d) ? d.map((e) => e.msg).join('; ') : (d ?? '')
  } catch {
    /* no JSON body */
  }
  return new ApiError(detail || `The server returned an error (HTTP ${res.status}).`, res.status)
}

async function doFetch(path, init) {
  try {
    return await fetch(`${API_URL}${path}`, init)
  } catch (e) {
    if (e?.name === 'AbortError') throw e
    throw new ApiError(
      "Can't reach the server. If it was idle, the free host can take 30-60 seconds to wake up; try again.",
      0,
    )
  }
}

async function getJson(path, { signal, params } = {}) {
  const qs = params ? toQuery(params) : ''
  const res = await doFetch(`${path}${qs}`, { signal })
  if (!res.ok) throw await errorFromResponse(res)
  return res.json()
}

/** Query string from an object; skips empty values and repeats keys for arrays. */
export function toQuery(params) {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, x))
    else if (v !== undefined && v !== null && v !== '') sp.append(k, v)
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

/** Filters with the empty ones dropped (and parliament as a number). */
export function cleanFilters(filters = {}) {
  const out = {}
  for (const [k, v] of Object.entries(filters)) {
    if (v === '' || v === null || v === undefined) continue
    if (Array.isArray(v) && v.length === 0) continue
    out[k] = k === 'parliament' ? Number(v) : v
  }
  return out
}

/** Request body for /search and /ask: the trimmed query plus only the filters that are set. */
export function buildBody(query, filters = {}, extra = {}) {
  return { query: query.trim(), ...extra, ...cleanFilters(filters) }
}

export const getFilters = (opts) => getJson('/filters', opts)

export const getSpeakers = (q, opts) =>
  getJson('/filters/speakers', { ...opts, params: { q } }).then((d) => d.speakers)

export function getTrend({ query, groupBy = 'none', filters = {} }, opts) {
  const { date_from, date_to, party, speaker, domains, parliament, bill } = filters
  return getJson('/stats/trend', {
    ...opts,
    params: { q: query, group_by: groupBy, date_from, date_to, party, speaker, domains, parliament, bill },
  })
}

export async function postJson(path, body, { signal } = {}) {
  const res = await doFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) throw await errorFromResponse(res)
  return res
}

export async function search(body, opts) {
  return (await postJson('/search', body, opts)).json()
}

/**
 * Parse a server-sent-events byte stream into { event, data } objects. Events may be split across
 * network chunks; malformed JSON is skipped rather than crashing the stream.
 */
export async function* parseSSE(stream) {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const emit = (block) => {
    let event = 'message'
    const data = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
    }
    if (!data.length) return null
    try {
      return { event, data: JSON.parse(data.join('\n')) }
    } catch {
      return null
    }
  }
  try {
    for (;;) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      buffer = buffer.replace(/\r\n/g, '\n')
      let i
      while ((i = buffer.indexOf('\n\n')) !== -1) {
        const ev = emit(buffer.slice(0, i))
        buffer = buffer.slice(i + 2)
        if (ev) yield ev
      }
      if (done) {
        const ev = buffer.trim() ? emit(buffer) : null
        if (ev) yield ev
        return
      }
    }
  } finally {
    reader.releaseLock?.()
  }
}

/** POST /ask and yield its events: sources, token, done, error. */
export async function* streamAsk(body, { signal } = {}) {
  const res = await postJson('/ask', body, { signal })
  yield* parseSSE(res.body)
}
