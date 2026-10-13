import { useCallback, useEffect, useRef, useState } from 'react'
import { streamAsk } from '../api/client'

const INITIAL = {
  status: 'idle', // idle | loading | streaming | done | error
  text: '',
  sources: [],
  cited: [],
  invalidCitations: [],
  unverifiedQuotes: [],
  outOfScope: false, // nothing in the record relates to the question; the LLM was not asked
  suggestions: [], // questions worth asking instead
  error: null,
}

/**
 * Runs POST /ask and exposes the streamed answer.
 *
 * `streamFn(body, { signal })` must return an async iterable of { event, data } and defaults to the
 * real API; tests pass a fake. Starting a new question aborts the previous one, and so does unmount.
 */
export function useStreamedAnswer(streamFn = streamAsk) {
  const [state, setState] = useState(INITIAL)
  const controller = useRef(null)

  const cancel = useCallback(() => {
    controller.current?.abort()
    controller.current = null
  }, [])

  const reset = useCallback(() => {
    cancel()
    setState(INITIAL)
  }, [cancel])

  const ask = useCallback(
    async (body) => {
      cancel()
      const ctl = new AbortController()
      controller.current = ctl
      setState({ ...INITIAL, status: 'loading' })
      try {
        for await (const { event, data } of streamFn(body, { signal: ctl.signal })) {
          if (ctl.signal.aborted) return
          if (event === 'sources') {
            setState((s) => ({ ...s, status: 'streaming', sources: data.sources }))
          } else if (event === 'token') {
            setState((s) => ({ ...s, status: 'streaming', text: s.text + data.text }))
          } else if (event === 'done') {
            setState((s) => ({
              ...s,
              status: 'done',
              cited: data.cited ?? [],
              invalidCitations: data.invalid_citations ?? [],
              unverifiedQuotes: data.unverified_quotes ?? [],
              outOfScope: Boolean(data.out_of_scope),
              suggestions: data.suggestions ?? [],
            }))
          } else if (event === 'error') {
            setState((s) => ({ ...s, status: 'error', error: data.message }))
            return
          }
        }
        // The stream ended without a `done` event: treat what arrived as final.
        setState((s) => (s.status === 'streaming' || s.status === 'loading' ? { ...s, status: 'done' } : s))
      } catch (e) {
        if (e?.name === 'AbortError' || ctl.signal.aborted) return
        setState((s) => ({ ...s, status: 'error', error: e?.message || 'Something went wrong.' }))
      }
    },
    [cancel, streamFn],
  )

  useEffect(() => cancel, [cancel])

  return { ...state, ask, cancel, reset }
}
