import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, buildBody, cleanFilters, parseSSE, streamAsk, toQuery } from './client'

/** A ReadableStream that delivers the given strings as separate network chunks. */
function streamOf(...chunks) {
  const enc = new TextEncoder()
  return new ReadableStream({
    start(c) {
      chunks.forEach((x) => c.enqueue(enc.encode(x)))
      c.close()
    },
  })
}

async function collect(it) {
  const out = []
  for await (const x of it) out.push(x)
  return out
}

afterEach(() => vi.unstubAllGlobals())

describe('parseSSE', () => {
  it('parses events and JSON data', async () => {
    const events = await collect(
      parseSSE(streamOf('event: token\ndata: {"text":"Hi"}\n\nevent: done\ndata: {"cited":[1]}\n\n')),
    )
    expect(events).toEqual([
      { event: 'token', data: { text: 'Hi' } },
      { event: 'done', data: { cited: [1] } },
    ])
  })

  it('reassembles events split across network chunks, even mid-character', async () => {
    const bytes = new TextEncoder().encode('event: token\ndata: {"text":"café"}\n\n')
    const cut = bytes.indexOf(0xc3) + 1 // between the two bytes of "é"
    const stream = new ReadableStream({
      start(c) {
        c.enqueue(bytes.slice(0, cut))
        c.enqueue(bytes.slice(cut))
        c.close()
      },
    })
    expect(await collect(parseSSE(stream))).toEqual([{ event: 'token', data: { text: 'café' } }])
  })

  it('handles CRLF line endings and a final event with no trailing blank line', async () => {
    const events = await collect(parseSSE(streamOf('event: token\r\ndata: {"text":"a"}\r\n\r\nevent: done\ndata: {}')))
    expect(events.map((e) => e.event)).toEqual(['token', 'done'])
  })

  it('skips malformed events instead of failing the whole stream', async () => {
    const events = await collect(parseSSE(streamOf('event: token\ndata: {oops\n\nevent: token\ndata: {"text":"ok"}\n\n')))
    expect(events).toEqual([{ event: 'token', data: { text: 'ok' } }])
  })
})

describe('streamAsk errors', () => {
  const respond = (status, body) =>
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })))

  it('turns a 422 into the server validation message', async () => {
    respond(422, { detail: [{ msg: 'String should have at least 2 characters' }] })
    await expect(collect(streamAsk({ query: 'x' }))).rejects.toThrow(/at least 2 characters/)
  })

  it('gives a plain message when the index is not ready (503)', async () => {
    respond(503, { detail: 'whatever' })
    await expect(collect(streamAsk({ query: 'carbon' }))).rejects.toThrow(/not available/)
  })

  it('explains an unreachable server, mentioning the sleeping free host', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const err = await collect(streamAsk({ query: 'carbon' })).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toMatch(/30-60 seconds/)
  })

  it('lets aborts through untouched so callers can ignore them', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')))
    const err = await collect(streamAsk({ query: 'carbon' })).catch((e) => e)
    expect(err.name).toBe('AbortError')
  })

  it('posts JSON to /ask and yields the parsed events', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(streamOf('event: done\ndata: {"cited":[]}\n\n')))
    vi.stubGlobal('fetch', fetchMock)
    const events = await collect(streamAsk({ query: 'carbon pricing' }))
    expect(events).toEqual([{ event: 'done', data: { cited: [] } }])
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/ask$/)
    expect(JSON.parse(init.body)).toEqual({ query: 'carbon pricing' })
  })
})

describe('request helpers', () => {
  it('drops empty filters and converts parliament to a number', () => {
    expect(
      cleanFilters({ date_from: '', party: 'NDP', domains: [], speaker: '', parliament: '44', date_to: '2024-01-01' }),
    ).toEqual({ party: 'NDP', parliament: 44, date_to: '2024-01-01' })
    expect(buildBody('  carbon tax  ', { party: 'NDP' }, { top_k: 5 })).toEqual({
      query: 'carbon tax',
      top_k: 5,
      party: 'NDP',
    })
  })

  it('builds query strings with repeated array keys', () => {
    expect(toQuery({ q: 'a b', domains: ['x', 'y'], party: '', gone: undefined })).toBe('?q=a+b&domains=x&domains=y')
    expect(toQuery({})).toBe('')
  })
})
