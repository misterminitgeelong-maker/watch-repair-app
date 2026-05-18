/** Resize camera/gallery images before upload or preview (reduces mobile WebView memory pressure). */
export class ImageCompressionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ImageCompressionError'
  }
}

export function compressImage(file: File, maxDim = 1500, quality = 0.8): Promise<File> {
  return new Promise((resolve, reject) => {
    if (!file.type.startsWith('image/')) {
      resolve(file)
      return
    }
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      let { width, height } = img
      if (width > maxDim || height > maxDim) {
        if (width >= height) {
          height = Math.round((height / width) * maxDim)
          width = maxDim
        } else {
          width = Math.round((width / height) * maxDim)
          height = maxDim
        }
      }
      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        reject(new ImageCompressionError('Could not process this photo. Please retake or choose another image.'))
        return
      }
      ctx.drawImage(img, 0, 0, width, height)
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new ImageCompressionError('Could not compress this photo. Please retake or choose another image.'))
            return
          }
          resolve(new File([blob], file.name.replace(/\.[^.]+$/, '.jpg'), { type: 'image/jpeg' }))
        },
        'image/jpeg',
        quality,
      )
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new ImageCompressionError('Could not read this photo. Please retake or choose another image.'))
    }
    img.src = url
  })
}
