import { AlertTriangle, CheckCircle2, Loader2, WifiOff } from 'lucide-react'
import type { UploadProgress } from '@/lib/photoUpload'

type Props = {
  /** Null while nothing is in flight. */
  progress: UploadProgress | null
  /** Shown before/instead of photo progress, e.g. "Creating job ticket…". */
  stageMessage?: string | null
  offline?: boolean
}

function icon(phase: UploadProgress['phase'] | 'stage', offline: boolean) {
  if (offline) return <WifiOff size={15} aria-hidden="true" />
  if (phase === 'complete') return <CheckCircle2 size={15} aria-hidden="true" />
  if (phase === 'failed') return <AlertTriangle size={15} aria-hidden="true" />
  return <Loader2 size={15} aria-hidden="true" className="animate-spin" />
}

/**
 * Live status for an intake submission: preparing → uploading X of Y →
 * retrying → complete/failed. Rendered in a polite live region, with an icon
 * plus wording so status never depends on colour alone.
 */
export default function IntakeSubmitStatus({ progress, stageMessage, offline = false }: Props) {
  const phase = progress?.phase ?? 'idle'
  const message = progress && progress.phase !== 'idle' ? progress.message : stageMessage
  if (!message) return null

  const tone =
    phase === 'failed'
      ? { color: 'var(--ms-error)', bg: 'color-mix(in srgb, var(--ms-error) 10%, transparent)' }
      : phase === 'retrying' || offline
        ? { color: '#6A4A10', bg: 'rgba(180,120,40,0.16)' }
        : phase === 'complete'
          ? { color: '#1F6D4C', bg: '#F0FAF0' }
          : { color: 'var(--ms-text-mid)', bg: 'var(--ms-bg)' }

  const showBar = progress != null && progress.total > 0 && phase !== 'idle'
  const pct = showBar ? Math.round((progress.completed / progress.total) * 100) : 0

  return (
    <div
      role="status"
      aria-live="polite"
      className="mt-3 rounded-lg px-3 py-2.5 text-sm"
      style={{ backgroundColor: tone.bg, color: tone.color }}
    >
      <p className="flex items-center gap-2">
        {icon(progress ? phase : 'stage', offline)}
        <span>{message}</span>
      </p>
      {showBar && (
        <div
          className="mt-2 h-1.5 w-full overflow-hidden rounded-full"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={progress.total}
          aria-valuenow={progress.completed}
          aria-label="Photo upload progress"
          style={{ backgroundColor: 'var(--ms-border)' }}
        >
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: `${pct}%`, backgroundColor: 'currentColor' }}
          />
        </div>
      )}
    </div>
  )
}
