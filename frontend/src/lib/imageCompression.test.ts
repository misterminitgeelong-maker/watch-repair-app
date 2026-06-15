import { describe, it, expect } from 'vitest'
import { fitDimensions, parseImageDimensions, canFullDecodeSafely } from './imageCompression'

describe('fitDimensions', () => {
  it('preserves aspect ratio when capping the long side', () => {
    expect(fitDimensions(6000, 4000, 1500, 2_250_000)).toEqual({ width: 1500, height: 1000 })
    expect(fitDimensions(4000, 6000, 1500, 2_250_000)).toEqual({ width: 1000, height: 1500 })
  })

  it('leaves small images untouched', () => {
    expect(fitDimensions(800, 600, 1500, 2_250_000)).toEqual({ width: 800, height: 600 })
  })

  it('applies the pixel cap after the dimension cap', () => {
    // 1500x1500 = 2.25M is exactly at the cap; a wider square would be scaled down
    const r = fitDimensions(3000, 3000, 2000, 2_250_000)
    expect(r.width * r.height).toBeLessThanOrEqual(2_250_000)
  })
})

describe('parseImageDimensions', () => {
  it('reads PNG dimensions from IHDR', () => {
    const b = new Uint8Array(24)
    b.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]) // signature
    const view = new DataView(b.buffer)
    view.setUint32(16, 4000) // width
    view.setUint32(20, 3000) // height
    expect(parseImageDimensions(b)).toEqual({ width: 4000, height: 3000 })
  })

  it('reads JPEG dimensions from the SOF0 marker', () => {
    // FF D8 (SOI) | FF C0 (SOF0) len=0x11 precision=8 height width ...
    const b = new Uint8Array([
      0xff, 0xd8,
      0xff, 0xc0, 0x00, 0x11, 0x08,
      0x0b, 0xb8, // height = 3000
      0x0f, 0xa0, // width = 4000
      0x03, 0x01, 0x22, 0x00,
    ])
    expect(parseImageDimensions(b)).toEqual({ width: 4000, height: 3000 })
  })

  it('skips JPEG app segments before the SOF marker', () => {
    // FF D8 | FF E0 (APP0) len=4 + 2 bytes payload | FF C0 ...
    const b = new Uint8Array([
      0xff, 0xd8,
      0xff, 0xe0, 0x00, 0x04, 0xaa, 0xbb,
      0xff, 0xc0, 0x00, 0x11, 0x08,
      0x01, 0x2c, // height = 300
      0x01, 0x90, // width = 400
      0x03, 0x01, 0x22, 0x00,
    ])
    expect(parseImageDimensions(b)).toEqual({ width: 400, height: 300 })
  })

  it('reads GIF dimensions', () => {
    const b = new Uint8Array(10)
    b.set([0x47, 0x49, 0x46, 0x38, 0x39, 0x61]) // GIF89a
    const view = new DataView(b.buffer)
    view.setUint16(6, 320, true)
    view.setUint16(8, 240, true)
    expect(parseImageDimensions(b)).toEqual({ width: 320, height: 240 })
  })

  it('returns null for unrecognised formats (e.g. HEIC)', () => {
    // HEIC starts with an ftyp box; we deliberately don't parse it.
    const heic = new Uint8Array([0x00, 0x00, 0x00, 0x18, 0x66, 0x74, 0x79, 0x70, 0x68, 0x65, 0x69, 0x63])
    expect(parseImageDimensions(heic)).toBeNull()
    expect(parseImageDimensions(new Uint8Array([1, 2, 3]))).toBeNull()
  })
})

describe('canFullDecodeSafely', () => {
  it('allows normal-resolution images', () => {
    expect(canFullDecodeSafely({ width: 4032, height: 3024 }, 5_000_000)).toBe(true) // 12MP
  })

  it('blocks a full-res decode of a very high-megapixel image (crash guard)', () => {
    expect(canFullDecodeSafely({ width: 8064, height: 6048 }, 9_000_000)).toBe(false) // 48MP
  })

  it('falls back to file size when dimensions are unknown (HEIC)', () => {
    expect(canFullDecodeSafely(null, 3 * 1024 * 1024)).toBe(true)
    expect(canFullDecodeSafely(null, 12 * 1024 * 1024)).toBe(false)
  })
})
