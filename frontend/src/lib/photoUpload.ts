import axios from 'axios'
import { compressImage, ImageCompressionError } from '@/lib/imageCompression'
import { getUploadErrorMessage } from '@/lib/api'

const UPLOAD_TIMEOUT_MS = 120000

/** Compress a camera/gallery file for in-memory preview or upload. */
export async function preparePhotoFile(file: File): Promise<File> {
  if (file.type.startsWith('image/')) return compressImage(file)
  return file
}

export function isLikelyMemoryError(err: unknown): boolean {
  const s = (err instanceof Error ? err.message : String(err)).toLowerCase()
  return (
    s.includes('memory') ||
    s.includes('oom') ||
    s.includes('out of memory') ||
    s.includes('not enough memory') ||
    s.includes('aw, snap') ||
    s.includes('allocation')
  )
}

export function getPhotoPrepareErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ImageCompressionError) return err.message
  if (isLikelyMemoryError(err)) {
    return 'The device ran low on memory. Close other apps, then retake photos one at a time and try again.'
  }
  return getUploadErrorMessage(err, fallback)
}

export function getIntakeSubmitErrorMessage(err: unknown, fallback: string): string {
  if (isLikelyMemoryError(err)) {
    return 'Could not complete the job ticket — the device ran low on memory. Close other apps and try again; photos can be added from the job page if the ticket was created.'
  }
  return getUploadErrorMessage(err, getUploadErrorMessage(err, fallback))
}

/** Let the browser breathe between heavy uploads on constrained devices. */
export async function yieldToMainThread(): Promise<void> {
  await new Promise<void>(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  })
}

/** Upload files one-by-one or in parallel on desktop. */
export async function uploadFilesSequential<T>(
  files: File[],
  uploadOne: (file: File) => Promise<T>,
  options?: { parallelOnWeb?: boolean },
): Promise<T[]> {
  if (options?.parallelOnWeb) return Promise.all(files.map(uploadOne))
  const results: T[] = []
  for (const file of files) {
    results.push(await uploadOne(file))
    await yieldToMainThread()
  }
  return results
}

// ── Retry ─────────────────────────────────────────────────────────────────────

/** Attempts per upload, including the first try. */
export const UPLOAD_MAX_ATTEMPTS = 3
/** First backoff step; doubles per attempt and is capped by UPLOAD_RETRY_MAX_DELAY_MS. */
export const UPLOAD_RETRY_BASE_DELAY_MS = 800
export const UPLOAD_RETRY_MAX_DELAY_MS = 6_000

export const OFFLINE_UPLOAD_MESSAGE =
  'No internet connection. Photos will need to be added from the job page once you are back online.'

export function isOffline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}

/**
 * Transient failures worth another attempt: dropped connections, timeouts,
 * rate limits and server errors. Client errors (400/401/403/404/413/422) are
 * permanent — retrying only wastes the tech's time and battery.
 */
export function isRetryableUploadError(err: unknown): boolean {
  if (axios.isAxiosError(err)) {
    if (err.code === 'ERR_CANCELED') return false
    const status = err.response?.status
    // No response at all: network drop, DNS failure or timeout.
    if (status == null) return true
    if (status === 408 || status === 429) return true
    return status >= 500 && status < 600
  }
  if (err instanceof ImageCompressionError) return false
  if (isLikelyMemoryError(err)) return false
  if (err instanceof Error) {
    const s = err.message.toLowerCase()
    return s.includes('network') || s.includes('timeout') || s.includes('timed out') || s.includes('failed to fetch')
  }
  return false
}

/** Exponential backoff, capped. `attempt` is 1-based (delay *before* attempt+1). */
export function uploadRetryDelayMs(
  attempt: number,
  baseMs = UPLOAD_RETRY_BASE_DELAY_MS,
  maxMs = UPLOAD_RETRY_MAX_DELAY_MS,
): number {
  const exponential = baseMs * 2 ** Math.max(0, attempt - 1)
  return Math.min(maxMs, exponential)
}

export type RetryOptions = {
  attempts?: number
  /** Called before each retry with the 1-based number of the attempt that failed. */
  onRetry?: (attempt: number, err: unknown) => void
  /** Injectable for tests. */
  sleep?: (ms: number) => Promise<void>
  /** Injectable for tests. */
  offline?: () => boolean
  baseDelayMs?: number
}

export class OfflineUploadError extends Error {
  constructor(message = OFFLINE_UPLOAD_MESSAGE) {
    super(message)
    this.name = 'OfflineUploadError'
  }
}

const defaultSleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

/**
 * Run an upload with bounded retries and exponential backoff.
 *
 * Going offline stops the loop immediately: repeatedly firing requests at a
 * dead radio drains the battery and tells the user nothing useful.
 */
export async function uploadWithRetry<T>(run: () => Promise<T>, options: RetryOptions = {}): Promise<T> {
  const attempts = Math.max(1, options.attempts ?? UPLOAD_MAX_ATTEMPTS)
  const sleep = options.sleep ?? defaultSleep
  const checkOffline = options.offline ?? isOffline
  if (checkOffline()) throw new OfflineUploadError()

  let lastError: unknown
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await run()
    } catch (err) {
      lastError = err
      const isLast = attempt >= attempts
      if (isLast || !isRetryableUploadError(err)) throw err
      if (checkOffline()) throw new OfflineUploadError()
      options.onRetry?.(attempt, err)
      await sleep(uploadRetryDelayMs(attempt, options.baseDelayMs))
      if (checkOffline()) throw new OfflineUploadError()
    }
  }
  throw lastError
}

// ── Batch progress ────────────────────────────────────────────────────────────

export type UploadPhase = 'idle' | 'preparing' | 'uploading' | 'retrying' | 'complete' | 'failed'

export type UploadProgress = {
  phase: UploadPhase
  /** Uploads finished successfully so far. */
  completed: number
  total: number
  /** Uploads that exhausted their attempts. */
  failed: number
  /** 1-based attempt number for the item in flight. */
  attempt: number
  /** Human-readable status line, safe to render in a live region. */
  message: string
}

export function describeUploadProgress(progress: UploadProgress): string {
  const { phase, completed, total, failed, attempt } = progress
  switch (phase) {
    case 'preparing':
      return total > 0 ? `Preparing ${total} photo${total === 1 ? '' : 's'}…` : 'Preparing…'
    case 'uploading':
      return `Uploading photo ${Math.min(completed + 1, total)} of ${total}…`
    case 'retrying':
      return `Connection problem — retrying photo ${Math.min(completed + 1, total)} of ${total} (attempt ${attempt + 1})…`
    case 'complete':
      return failed > 0
        ? `${completed} of ${total} photo${total === 1 ? '' : 's'} uploaded — ${failed} failed.`
        : `All ${total} photo${total === 1 ? '' : 's'} uploaded.`
    case 'failed':
      return `Photo upload failed — ${completed} of ${total} uploaded.`
    default:
      return ''
  }
}

export function initialUploadProgress(total = 0): UploadProgress {
  return { phase: 'idle', completed: 0, total, failed: 0, attempt: 1, message: '' }
}

export type UploadBatchItem<F> = {
  file: F
  /** Shown in per-photo failure messages, e.g. "Front (dial)". */
  label?: string
}

export type UploadBatchResult<F> = {
  uploaded: number
  failures: Array<{ item: UploadBatchItem<F>; error: unknown }>
}

/**
 * Upload a batch sequentially with retries, reporting aggregate progress.
 *
 * Never throws for a single failed photo: the job ticket already exists by the
 * time photos upload, so the caller reports which photos need re-adding instead
 * of failing (and risking a duplicate ticket).
 */
export async function uploadBatchWithRetry<F>(
  items: Array<UploadBatchItem<F>>,
  uploadOne: (file: F) => Promise<unknown>,
  options: RetryOptions & { onProgress?: (progress: UploadProgress) => void } = {},
): Promise<UploadBatchResult<F>> {
  const total = items.length
  const failures: UploadBatchResult<F>['failures'] = []
  let completed = 0

  const report = (phase: UploadPhase, attempt = 1) => {
    const progress: UploadProgress = {
      phase,
      completed,
      total,
      failed: failures.length,
      attempt,
      message: '',
    }
    progress.message = describeUploadProgress(progress)
    options.onProgress?.(progress)
  }

  if (total === 0) {
    report('complete')
    return { uploaded: 0, failures }
  }

  for (const item of items) {
    report('uploading')
    try {
      await uploadWithRetry(() => uploadOne(item.file), {
        ...options,
        onRetry: (attempt, err) => {
          report('retrying', attempt)
          options.onRetry?.(attempt, err)
        },
      })
      completed += 1
    } catch (err) {
      failures.push({ item, error: err })
      // An offline batch will not recover mid-run — stop firing requests.
      if (err instanceof OfflineUploadError) {
        for (const remaining of items.slice(completed + failures.length)) {
          failures.push({ item: remaining, error: err })
        }
        break
      }
    }
    await yieldToMainThread()
  }

  report(failures.length > 0 && completed === 0 ? 'failed' : 'complete')
  return { uploaded: completed, failures }
}

/** One sentence naming the photos that still need adding from the job page. */
export function describeUploadFailures<F>(failures: UploadBatchResult<F>['failures']): string | null {
  if (failures.length === 0) return null
  if (failures.some(f => f.error instanceof OfflineUploadError)) {
    return `${failures.length} photo${failures.length === 1 ? '' : 's'} could not be uploaded — you went offline. The ticket was created; add the photos from the job page.`
  }
  const labels = failures.map(f => f.item.label).filter((l): l is string => Boolean(l))
  const named = labels.length ? ` (${labels.join(', ')})` : ''
  const first = getUploadErrorMessage(failures[0].error, '')
  const detail = first ? ` ${first}` : ''
  return `${failures.length} photo${failures.length === 1 ? '' : 's'}${named} could not be uploaded after several attempts. The ticket was created — add the photos from the job page.${detail}`
}

export { UPLOAD_TIMEOUT_MS }
