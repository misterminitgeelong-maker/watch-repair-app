import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import IntakeSubmitStatus from './IntakeSubmitStatus'
import { describeUploadProgress, initialUploadProgress, type UploadProgress } from '@/lib/photoUpload'

function progress(patch: Partial<UploadProgress>): UploadProgress {
  const merged = { ...initialUploadProgress(3), ...patch }
  return { ...merged, message: describeUploadProgress(merged) }
}

describe('IntakeSubmitStatus', () => {
  it('renders nothing when nothing is in flight', () => {
    const { container } = render(<IntakeSubmitStatus progress={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the creation stage before photos start uploading', () => {
    render(<IntakeSubmitStatus progress={null} stageMessage="Creating job ticket…" />)
    expect(screen.getByRole('status')).toHaveTextContent('Creating job ticket…')
  })

  it('walks through uploading, retrying and complete', () => {
    const { rerender } = render(<IntakeSubmitStatus progress={progress({ phase: 'uploading', completed: 0 })} />)
    expect(screen.getByRole('status')).toHaveTextContent('Uploading photo 1 of 3…')

    rerender(<IntakeSubmitStatus progress={progress({ phase: 'retrying', completed: 1, attempt: 2 })} />)
    expect(screen.getByRole('status')).toHaveTextContent(/retrying photo 2 of 3 \(attempt 3\)/i)

    rerender(<IntakeSubmitStatus progress={progress({ phase: 'complete', completed: 3 })} />)
    expect(screen.getByRole('status')).toHaveTextContent('All 3 photos uploaded.')
  })

  it('exposes upload progress to assistive tech', () => {
    render(<IntakeSubmitStatus progress={progress({ phase: 'uploading', completed: 2 })} />)
    const bar = screen.getByRole('progressbar', { name: /photo upload progress/i })
    expect(bar).toHaveAttribute('aria-valuenow', '2')
    expect(bar).toHaveAttribute('aria-valuemax', '3')
  })

  it('reports a failed batch in words, not only colour', () => {
    render(<IntakeSubmitStatus progress={progress({ phase: 'failed', failed: 3 })} />)
    expect(screen.getByRole('status')).toHaveTextContent('Photo upload failed — 0 of 3 uploaded.')
  })

  it('announces politely so it does not interrupt the form', () => {
    render(<IntakeSubmitStatus progress={progress({ phase: 'uploading' })} offline />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })
})
