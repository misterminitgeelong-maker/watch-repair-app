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

/**
 * Largest source image (in megapixels) we'll decode at full resolution via the
 * HTMLImageElement fallback. A modern phone "Pro" camera shoots 48MP (~190MB
 * decoded) which OOM-crashes the tab on mobile — beyond this cap we refuse the
 * full-res decode and surface a friendly error instead of crashing.
 */
const FALLBACK_MAX_SOURCE_PIXELS = 24_000_000
/** When intrinsic size is unknown (e.g. HEIC), use file size as a proxy for the same guard. */
const FALLBACK_MAX_SOURCE_BYTES = 8 * 1024 * 1024

const TOO_LARGE_MESSAGE =
  'This photo is too large for this device to process. Switch your camera to "Most Compatible" / JPEG (iPhone: Settings → Camera → Formats), or add the photo later from the job page.'

export function fitDimensions(width: number, height: number, maxDim: number, maxPixels: number) {
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

/**
 * Read intrinsic dimensions from the file header without decoding pixels, so we
 * can resize aspect-correctly and decide whether a full-res decode is safe.
 * Only reads the first chunk of the file (tiny memory). Returns null for
 * formats we don't parse (e.g. HEIC/HEIF).
 */
export function parseImageDimensions(bytes: Uint8Array): { width: number; height: number } | null {
  // PNG: 8-byte signature, then IHDR (width @16, height @20, big-endian).
  if (
    bytes.length >= 24 &&
    bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47
  ) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    return { width: view.getUint32(16), height: view.getUint32(20) }
  }

  // GIF: 'GIF87a'/'GIF89a', width/height little-endian @6.
  if (bytes.length >= 10 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    return { width: view.getUint16(6, true), height: view.getUint16(8, true) }
  }

  // JPEG: scan segments for a Start-Of-Frame marker (SOFn), read height/width.
  if (bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
    let offset = 2
    while (offset + 9 < bytes.length) {
      if (view.getUint8(offset) !== 0xff) { offset++; continue }
      const marker = view.getUint8(offset + 1)
      // SOF0..SOF15 carry the frame dimensions, excluding DHT(C4)/JPG(C8)/DAC(CC).
      if (
        marker >= 0xc0 && marker <= 0xcf &&
        marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc
      ) {
        const height = view.getUint16(offset + 5)
        const width = view.getUint16(offset + 7)
        if (width > 0 && height > 0) return { width, height }
        return null
      }
      // Standalone markers (no length): RSTn / SOI / EOI / TEM.
      if (marker === 0xd8 || marker === 0xd9 || (marker >= 0xd0 && marker <= 0xd7) || marker === 0x01) {
        offset += 2
        continue
      }
      const segmentLength = view.getUint16(offset + 2)
      if (segmentLength < 2) return null
      offset += 2 + segmentLength
    }
  }

  return null
}

async function readImageDimensions(file: File): Promise<{ width: number; height: number } | null> {
  try {
    const head = file.size > 512 * 1024 ? file.slice(0, 512 * 1024) : file
    const buf = new Uint8Array(await head.arrayBuffer())
    return parseImageDimensions(buf)
  } catch {
    return null
  }
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
  dims: { width: number; height: number } | null,
): Promise<File | null> {
  if (typeof createImageBitmap !== 'function') return null
  try {
    // When intrinsic dimensions are known, request an aspect-correct target so
    // the bitmap is both the right shape and memory-bounded. When unknown
    // (e.g. HEIC), cap each side to maxDim as a best-effort.
    const target = dims
      ? fitDimensions(dims.width, dims.height, opts.maxDim, opts.maxPixels)
      : { width: opts.maxDim, height: opts.maxDim }
    const bitmap = await createImageBitmap(file, {
      resizeWidth: target.width,
      resizeHeight: target.height,
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

/**
 * Is it safe to decode this image at full resolution via HTMLImageElement?
 * A full-res decode of a very large image OOM-crashes the browser tab on
 * mobile, which no try/catch can recover from — so we gate it.
 */
export function canFullDecodeSafely(
  dims: { width: number; height: number } | null,
  fileSize: number,
): boolean {
  if (dims) return dims.width * dims.height <= FALLBACK_MAX_SOURCE_PIXELS
  return fileSize <= FALLBACK_MAX_SOURCE_BYTES
}

export function compressImage(file: File, options?: Partial<CompressionOptions>): Promise<File> {
  if (!file.type.startsWith('image/')) {
    return Promise.resolve(file)
  }
  const opts = { ...getCompressionOptions(), ...options }
  return (async () => {
    const dims = await readImageDimensions(file)

    // Primary path: createImageBitmap resizes during decode (memory-bounded).
    const fromBitmap = await compressWithCreateImageBitmap(file, opts, dims)
    if (fromBitmap) return fromBitmap

    // Fallback decodes at full resolution — only attempt it when that won't
    // blow the device's memory. Otherwise fail gracefully so the ticket can
    // still be created (the photo can be added later from the job page).
    if (!canFullDecodeSafely(dims, file.size)) {
      throw new ImageCompressionError(TOO_LARGE_MESSAGE)
    }
    return compressWithHtmlImage(file, opts)
  })()
}
