import { Camera, CameraResultType, CameraSource } from '@capacitor/camera'
import { isNativeApp } from '@/lib/native'

/** Take a photo with the native camera and return it as a File, or null if cancelled / not native. */
export async function takeNativePhoto(): Promise<File | null> {
  if (!isNativeApp) return null
  try {
    const photo = await Camera.getPhoto({ quality: 80, resultType: CameraResultType.Uri, source: CameraSource.Camera })
    if (!photo.webPath) return null
    const blob = await (await fetch(photo.webPath)).blob()
    return new File([blob], `photo-${Date.now()}.${photo.format || 'jpg'}`, { type: blob.type || 'image/jpeg' })
  } catch {
    return null
  }
}
