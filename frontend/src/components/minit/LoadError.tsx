import { getApiErrorMessage } from '@/lib/api'
import { Button, Card } from '@/components/ui'

/**
 * A failed HQ load, said as a failure. Without this, screens fell back to
 * their empty state ("No shops", "Nothing in the inbox") or spun forever, so
 * HQ staff read an outage as an empty network.
 */
export function LoadError({
  error,
  message,
  onRetry,
  className = 'mb-6',
}: {
  error: unknown
  message: string
  onRetry: () => void
  className?: string
}) {
  const detail = getApiErrorMessage(error, '')
  return (
    <Card className={className}>
      <div role="alert" className="p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm">
          <p style={{ color: 'var(--ms-error)' }}>{message}</p>
          {detail && detail !== message && (
            <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>{detail}</p>
          )}
        </div>
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      </div>
    </Card>
  )
}
