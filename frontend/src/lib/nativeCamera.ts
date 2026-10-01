import { Camera, CameraResultType, CameraSource } from '@capacitor/camera'
import { isNativeApp } from '@/lib/native'

/** Take a photo with the native camera and return it as a compressed File, or null if cancelled / not native. */
export async function takeNativePhoto(): Promise<File | null> {
  if (!isNativeApp) return null
  try {
    const photo = await Camera.getPhoto({
      quality: 80,
      width: 1600,
      height: 1600,
      correctOrientation: true,
      saveToGallery: false,
      resultType: CameraResultType.Uri,
      source: CameraSource.Camera,
    })
    if (!photo.webPath) return null
    const blob = await (await fetch(photo.webPath)).blob()
    return new File([blob], `photo-${Date.now()}.${photo.format || 'jpg'}`, { type: blob.type || 'image/jpeg' })
  } catch {
    return null
  }
}

/**
 * In the phone app, route every "take a photo" file input (`<input type="file" capture>`)
 * through the native camera: smaller uploads and no flaky web file chooser. The page's own
 * change handlers still run, because the photo is handed back through the input.
 */
export function installNativeCameraBridge(): void {
  if (!isNativeApp) return
  document.addEventListener(
    'click',
    (event) => {
      const input = event.target
      if (!(input instanceof HTMLInputElement) || input.type !== 'file' || !input.hasAttribute('capture')) return
      event.preventDefault()
      void takeNativePhoto().then((file) => {
        if (!file) return
        const transfer = new DataTransfer()
        transfer.items.add(file)
        input.files = transfer.files
        input.dispatchEvent(new Event('change', { bubbles: true }))
      })
    },
    true,
  )
}
