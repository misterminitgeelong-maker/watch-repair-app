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

export { UPLOAD_TIMEOUT_MS }
