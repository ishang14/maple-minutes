import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import CitationCard from './CitationCard'

const SOURCE = {
  n: 3,
  speaker: 'Mrs. Tracy Gray',
  party: 'Conservative',
  riding: 'Kelowna—Lake Country',
  role: 'Shadow Minister',
  date: '2023-02-07',
  heading: 'Business of Supply',
  bill: 'C-8',
  domains: ['finance_economy'],
  text: 'The carbon tax is a burden.\nIt hurts families.',
  source_url: 'https://www.ourcommons.ca/DocumentViewer/en/44-1/house/sitting-155/hansard#Int-1',
}

function Harness(props) {
  const [open, setOpen] = useState(false)
  return <CitationCard source={SOURCE} expanded={open} onToggle={() => setOpen((o) => !o)} {...props} />
}

describe('CitationCard', () => {
  it('shows speaker, party, date and heading collapsed, without the speech', () => {
    render(<Harness />)
    expect(screen.getByText('Mrs. Tracy Gray (Conservative)')).toBeInTheDocument()
    expect(screen.getByText('2023-02-07 · Business of Supply')).toBeInTheDocument()
    expect(screen.queryByText(/carbon tax is a burden/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { expanded: false })).toBeInTheDocument()
  })

  it('expands to the excerpt, metadata and a safe link to the official sitting, and collapses again', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('button'))
    expect(screen.getByText(/carbon tax is a burden/)).toBeInTheDocument()
    expect(screen.getByText('Kelowna—Lake Country')).toBeInTheDocument()
    expect(screen.getByText('C-8')).toBeInTheDocument()
    expect(screen.getByText('Finance, economy and taxation')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /Open in the official Hansard/ })
    expect(link).toHaveAttribute('href', SOURCE.source_url)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
    await userEvent.click(screen.getByRole('button'))
    expect(screen.queryByText(/carbon tax is a burden/)).not.toBeInTheDocument()
  })

  it('has an id the citation chips can scroll to, and can be highlighted', () => {
    const { container } = render(<Harness highlighted />)
    const card = container.querySelector('#citation-3')
    expect(card).not.toBeNull()
    expect(card.className).toContain('ring-2')
  })

  it('copes with missing speaker metadata', () => {
    render(<CitationCard source={{ ...SOURCE, speaker: null, party: null }} expanded={false} onToggle={() => {}} />)
    expect(screen.getByText('Unknown speaker')).toBeInTheDocument()
  })
})
