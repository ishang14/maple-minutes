import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AnswerView from './AnswerView'

const SOURCES = [
  { n: 1, speaker: 'Jane Doe', date: '2023-05-01' },
  { n: 2, speaker: 'John Roe', date: '2023-06-02' },
]

const view = (props = {}) =>
  render(<AnswerView text="" sources={SOURCES} status="done" onCite={() => {}} {...props} />)

describe('AnswerView citations', () => {
  it('turns [n] into clickable chips that report the source number', async () => {
    const onCite = vi.fn()
    view({ text: 'Carbon pricing was debated [1] and defended [2].', onCite })
    const chips = screen.getAllByRole('button')
    expect(chips.map((c) => c.textContent)).toEqual(['1', '2'])
    await userEvent.click(screen.getByRole('button', { name: /Source 2: John Roe, 2023-06-02/ }))
    expect(onCite).toHaveBeenCalledWith(2)
    expect(screen.queryByText('[1]')).not.toBeInTheDocument() // the brackets are replaced by the chip
  })

  it('handles several adjacent citations like [1][2]', () => {
    view({ text: 'Both agreed [1][2].' })
    expect(screen.getAllByRole('button')).toHaveLength(2)
  })

  it('leaves numbers that are not real sources as plain text, not chips', () => {
    view({ text: 'A claim [7] and another [0].' })
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.getByText(/A claim \[7\] and another \[0\]\./)).toBeInTheDocument()
  })

  it('renders bullets and nested bullets as lists, with bold text', () => {
    view({ text: '- **Conservatives** argued [1]\n  - sub point [2]\n- Liberals replied' })
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(within(items[0]).getByText('Conservatives').tagName).toBe('STRONG')
    expect(screen.getAllByRole('list')).toHaveLength(1)
  })

  it('understands full-width bracket citations such as \u30101\u3011', async () => {
    const onCite = vi.fn()
    view({ text: 'Epilepsy is described as widespread \u30101\u3011.', onCite })
    const chip = screen.getByRole('button', { name: /Source 1/ })
    expect(chip).toHaveTextContent('1')
    expect(screen.queryByText(/\u3010/)).not.toBeInTheDocument()
    await userEvent.click(chip)
    expect(onCite).toHaveBeenCalledWith(1)
  })

  it('shows narrow and no-break spaces as ordinary spaces so names do not run together', () => {
    const { container } = view({ text: 'Mario\u202fBeaulieu and Ruby\u00a0Sahota spoke on October\u20097.' })
    expect(container.textContent).toBe('Mario Beaulieu and Ruby Sahota spoke on October 7.')
    expect(container.textContent).not.toMatch(/[\u00a0\u2009\u202f]/)
  })

  it('keeps punctuation after a chip on the same line as the chip', () => {
    view({ text: 'Carbon pricing was defended [1]. And opposed [2], loudly [1][2].' })
    const first = screen.getAllByRole('button')[0]
    expect(first.parentElement).toHaveTextContent(/^1\.$/) // the full stop travels with its chip
    expect(screen.getAllByRole('button')[1].parentElement).toHaveTextContent(/^2,$/)
    expect(screen.getAllByRole("button")).toHaveLength(4)
  })

  it('renders *italic* text as emphasis without showing the asterisks', () => {
    const { container } = view({ text: 'It was a *tax measure* rather than a plan. Also 2 * 3 stays.' })
    expect(container.querySelector('em')).toHaveTextContent('tax measure')
    expect(container).not.toHaveTextContent('*tax measure*')
    expect(container).toHaveTextContent('2 * 3 stays')
  })

  it('escapes HTML in the answer instead of rendering it', () => {
    view({ text: 'Say <img src=x onerror=alert(1)> **loud**' })
    expect(document.querySelector('img')).toBeNull()
    expect(screen.getByText(/<img src=x onerror=alert\(1\)>/)).toBeInTheDocument()
  })

  it('shows a typing cursor only while streaming', () => {
    const { container, rerender } = render(
      <AnswerView text="Hello" sources={SOURCES} status="streaming" onCite={() => {}} />,
    )
    expect(container.querySelector('.blink')).not.toBeNull()
    rerender(<AnswerView text="Hello" sources={SOURCES} status="done" onCite={() => {}} />)
    expect(container.querySelector('.blink')).toBeNull()
  })
})

describe('AnswerView quote and citation warnings', () => {
  it('lists unverified quotes with buttons that open the cited source', async () => {
    const onCite = vi.fn()
    view({
      text: 'He said something [1].',
      unverifiedQuotes: [{ quote: 'made it more expensive', cited: [1] }],
      onCite,
    })
    const note = screen.getByRole('note')
    expect(note).toHaveTextContent('Check these quotes against the source')
    expect(note).toHaveTextContent('“made it more expensive”')
    await userEvent.click(within(note).getByRole('button', { name: 'Open source 1' }))
    expect(onCite).toHaveBeenCalledWith(1)
  })

  it('shows no warnings for a clean answer, or while still streaming', () => {
    const { rerender } = render(
      <AnswerView text="Fine [1]." sources={SOURCES} status="done" unverifiedQuotes={[]} onCite={() => {}} />,
    )
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
    rerender(
      <AnswerView text="x" sources={SOURCES} status="streaming" unverifiedQuotes={[{ quote: 'q q q', cited: [] }]} onCite={() => {}} />,
    )
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('mentions source numbers that do not exist', () => {
    view({ text: 'Claim [9].', invalidCitations: [9] })
    expect(screen.getByRole('note')).toHaveTextContent('do not exist (9)')
  })
})
