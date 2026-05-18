import { Capacitor } from '@capacitor/core'
import { compressImage, ImageCompressionError } from '@/lib/imageCompression'
import { getUploadErrorMessage } from '@/lib/api'

const UPLOAD_TIMEOUT_MS = 120000

/** Compress a camera/gallery file for in-memory preview or upload. */
export async function preparePhotoFile(file: File): Promise<File> {
  if (file.type.startsWith('image/')) return compressImage(file)
  return file
}

export function getPhotoPrepareErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ImageCompressionError) return err.message
  return getUploadErrorMessage(err, fallback)
}

/** Upload files one-by-one on native (memory); optional parallel on desktop. */
export async function uploadFilesSequential<T>(
  files: File[],
  uploadOne: (file: File) => Promise<T>,
  options?: { parallelOnWeb?: boolean },
): Promise<T[]> {
  const parallel = options?.parallelOnWeb && !Capacitor.isNativePlatform()
  if (parallel) return Promise.all(files.map(uploadOne))
  const results: T[] = []
  for (const file of files) {
    results.push(await uploadOne(file))
  }
  return results
}

export { UPLOAD_TIMEOUT_MS }
