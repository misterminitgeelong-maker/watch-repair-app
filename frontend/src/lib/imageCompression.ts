/** Resize camera/gallery images before upload or preview (reduces memory pressure on mobile browsers). */
export class ImageCompressionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ImageCompressionError'
  }
}

export interface CompressionOptions {
  maxDim: number
  quality: number
  /** Cap total canvas pixels (avoids GPU/memory blow-ups on low-end devices). */
  maxPixels: number
}

export function getCompressionOptions(): CompressionOptions {
  return { maxDim: 1500, quality: 0.8, maxPixels: 2_250_000 }
}

function fitDimensions(width: number, height: number, maxDim: number, maxPixels: number) {
  let w = width
  let h = height
  if (w > maxDim || h > maxDim) {
    if (w >= h) {
      h = Math.round((h / w) * maxDim)
      w = maxDim
    } else {
      w = Math.round((w / h) * maxDim)
      h = maxDim
    }
  }
  const pixels = w * h
  if (pixels > maxPixels) {
    const scale = Math.sqrt(maxPixels / pixels)
    w = Math.max(1, Math.round(w * scale))
    h = Math.max(1, Math.round(h * scale))
  }
  return { width: w, height: h }
}

function canvasToJpegFile(
  source: CanvasImageSource,
  width: number,
  height: number,
  fileName: string,
  quality: number,
): Promise<File> {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return Promise.reject(
      new ImageCompressionError(
        'Could not process this photo. Try closing other apps, then retake with the camera (not gallery) if it keeps failing.',
      ),
    )
  }
  ctx.drawImage(source, 0, 0, width, height)
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(
            new ImageCompressionError(
              'Not enough memory to process this photo. Close other apps, then retake a photo (smaller file) and try again.',
            ),
          )
          return
        }
        resolve(new File([blob], fileName.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' }))
      },
      'image/jpeg',
      quality,
    )
  })
}

async function compressWithCreateImageBitmap(
  file: File,
  opts: CompressionOptions,
): Promise<File | null> {
  if (typeof createImageBitmap !== 'function') return null
  try {
    const bitmap = await createImageBitmap(file, {
      resizeWidth: opts.maxDim,
      resizeHeight: opts.maxDim,
      resizeQuality: 'high',
    })
    try {
      const { width, height } = fitDimensions(bitmap.width, bitmap.height, opts.maxDim, opts.maxPixels)
      return await canvasToJpegFile(bitmap, width, height, file.name, opts.quality)
    } finally {
      bitmap.close()
    }
  } catch {
    return null
  }
}

function compressWithHtmlImage(file: File, opts: CompressionOptions): Promise<File> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      const { width, height } = fitDimensions(img.width, img.height, opts.maxDim, opts.maxPixels)
      canvasToJpegFile(img, width, height, file.name, opts.quality).then(resolve).catch(reject)
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(
        new ImageCompressionError(
          'Could not read this photo. Retake with the camera or choose a smaller image from the gallery.',
        ),
      )
    }
    img.src = url
  })
}

export function compressImage(file: File, options?: Partial<CompressionOptions>): Promise<File> {
  if (!file.type.startsWith('image/')) {
    return Promise.resolve(file)
  }
  const opts = { ...getCompressionOptions(), ...options }
  return (async () => {
    const fromBitmap = await compressWithCreateImageBitmap(file, opts)
    if (fromBitmap) return fromBitmap
    return compressWithHtmlImage(file, opts)
  })()
}
