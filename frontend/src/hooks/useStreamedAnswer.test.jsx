import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useStreamedAnswer } from './useStreamedAnswer'

const SOURCES = [{ n: 1, chunk_id: 'a' }, { n: 2, chunk_id: 'b' }]

/** A fake stream function yielding the given events. */
const fake = (events) =>
  vi.fn(async function* () {
    for (const e of events) yield e
  })

/** A stream the test drives by hand: push() delivers an event, end() finishes it. */
function manualStream() {
  const queue = []
  let wake
  let ended = false
  const fn = vi.fn(async function* (_body, { signal }) {
    while (!signal.aborted) {
      if (queue.length) yield queue.shift()
      else if (ended) return
      else await new Promise((r) => (wake = r))
    }
  })
  return {
    fn,
    push: (e) => {
      queue.push(e)
      wake?.()
    },
    end: () => {
      ended = true
      wake?.()
    },
  }
}

describe('useStreamedAnswer', () => {
  it('starts idle', () => {
    const { result } = renderHook(() => useStreamedAnswer(fake([])))
    expect(result.current.status).toBe('idle')
    expect(result.current.text).toBe('')
  })

  it('collects sources, appends tokens in order, then reports citation info on done', async () => {
    const stream = fake([
      { event: 'sources', data: { sources: SOURCES } },
      { event: 'token', data: { text: 'Carbon ' } },
      { event: 'token', data: { text: 'pricing [1]' } },
      {
        event: 'done',
        data: { cited: [1], invalid_citations: [9], unverified_quotes: [{ quote: 'abc def ghi', cited: [1] }] },
      },
    ])
    const { result } = renderHook(() => useStreamedAnswer(stream))
    await act(() => result.current.ask({ query: 'carbon' }))
    expect(stream).toHaveBeenCalledWith({ query: 'carbon' }, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(result.current).toMatchObject({
      status: 'done',
      text: 'Carbon pricing [1]',
      sources: SOURCES,
      cited: [1],
      invalidCitations: [9],
      unverifiedQuotes: [{ quote: 'abc def ghi', cited: [1] }],
      error: null,
    })
  })

  it('shows loading, then streaming, while the answer arrives', async () => {
    const m = manualStream()
    const { result } = renderHook(() => useStreamedAnswer(m.fn))
    let finished
    act(() => {
      finished = result.current.ask({ query: 'carbon' })
    })
    expect(result.current.status).toBe('loading')
    await act(async () => m.push({ event: 'sources', data: { sources: SOURCES } }))
    await waitFor(() => expect(result.current.status).toBe('streaming'))
    await act(async () => m.push({ event: 'token', data: { text: 'Hello' } }))
    await waitFor(() => expect(result.current.text).toBe('Hello'))
    await act(async () => {
      m.push({ event: 'done', data: { cited: [] } })
      m.end()
      await finished
    })
    expect(result.current.status).toBe('done')
  })

  it('keeps the partial answer and surfaces the message on an error event', async () => {
    const stream = fake([
      { event: 'sources', data: { sources: SOURCES } },
      { event: 'token', data: { text: 'Partial' } },
      { event: 'error', data: { message: 'Groq rate limit reached (free tier).' } },
    ])
    const { result } = renderHook(() => useStreamedAnswer(stream))
    await act(() => result.current.ask({ query: 'carbon' }))
    expect(result.current).toMatchObject({
      status: 'error',
      text: 'Partial',
      error: 'Groq rate limit reached (free tier).',
    })
  })

  it('reports a failed request (network or HTTP) as an error', async () => {
    const stream = vi.fn(async function* () {
      yield* []
      throw new Error('Can\'t reach the server.')
    })
    const { result } = renderHook(() => useStreamedAnswer(stream))
    await act(() => result.current.ask({ query: 'carbon' }))
    expect(result.current.status).toBe('error')
    expect(result.current.error).toMatch(/reach the server/)
  })

  it('treats a stream that ends without "done" as finished', async () => {
    const stream = fake([
      { event: 'sources', data: { sources: SOURCES } },
      { event: 'token', data: { text: 'Cut off' } },
    ])
    const { result } = renderHook(() => useStreamedAnswer(stream))
    await act(() => result.current.ask({ query: 'carbon' }))
    expect(result.current.status).toBe('done')
    expect(result.current.text).toBe('Cut off')
  })

  it('aborts the previous question when a new one starts and ignores its late events', async () => {
    const first = manualStream()
    const second = fake([{ event: 'token', data: { text: 'second' } }, { event: 'done', data: { cited: [] } }])
    const fns = [first.fn, second]
    const { result } = renderHook(() => useStreamedAnswer((...a) => fns.shift()(...a)))
    act(() => {
      result.current.ask({ query: 'one' })
    })
    await act(async () => first.push({ event: 'token', data: { text: 'first' } }))
    await waitFor(() => expect(result.current.text).toBe('first'))
    const firstSignal = first.fn.mock.calls[0][1].signal
    await act(() => result.current.ask({ query: 'two' }))
    expect(firstSignal.aborted).toBe(true)
    await act(async () => first.push({ event: 'token', data: { text: ' LATE' } }))
    expect(result.current.text).toBe('second')
  })

  it('cancel() stops the stream and unmounting aborts it too', async () => {
    const m = manualStream()
    const { result, unmount } = renderHook(() => useStreamedAnswer(m.fn))
    act(() => {
      result.current.ask({ query: 'x' })
    })
    const signal = m.fn.mock.calls[0][1].signal
    act(() => result.current.cancel())
    expect(signal.aborted).toBe(true)

    const m2 = manualStream()
    const hook2 = renderHook(() => useStreamedAnswer(m2.fn))
    act(() => {
      hook2.result.current.ask({ query: 'y' })
    })
    hook2.unmount()
    expect(m2.fn.mock.calls[0][1].signal.aborted).toBe(true)
    unmount()
  })

  it('reset() returns to idle', async () => {
    const { result } = renderHook(() => useStreamedAnswer(fake([{ event: 'token', data: { text: 'x' } }])))
    await act(() => result.current.ask({ query: 'x' }))
    act(() => result.current.reset())
    expect(result.current.status).toBe('idle')
    expect(result.current.text).toBe('')
  })

  it('keeps the out-of-scope flag and the suggested questions from the done event', async () => {
    const stream = fake([
      { event: 'sources', data: { sources: [] } },
      { event: 'token', data: { text: 'I could not find anything related.' } },
      { event: 'done', data: { cited: [], out_of_scope: true, suggestions: ['What have MPs said about epilepsy?'] } },
    ])
    const { result } = renderHook(() => useStreamedAnswer(stream))
    await act(() => result.current.ask({ query: 'What is epilepsy?' }))
    expect(result.current).toMatchObject({
      status: 'done',
      outOfScope: true,
      suggestions: ['What have MPs said about epilepsy?'],
    })
  })

  it('defaults to in scope with no suggestions when the server sends neither', async () => {
    const stream = fake([{ event: 'done', data: { cited: [] } }])
    const { result } = renderHook(() => useStreamedAnswer(stream))
    await act(() => result.current.ask({ query: 'x' }))
    expect(result.current.outOfScope).toBe(false)
    expect(result.current.suggestions).toEqual([])
  })
})

