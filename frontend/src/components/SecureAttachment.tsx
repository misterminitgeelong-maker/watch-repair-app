import { useEffect, useState } from 'react'
import type { AnchorHTMLAttributes, ImgHTMLAttributes, ReactNode } from 'react'
import { resolveAttachmentDownloadUrl } from '@/lib/api'

function useResolvedAttachmentUrl(storageKey: string) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let canceled = false
    void resolveAttachmentDownloadUrl(storageKey)
      .then((nextUrl) => {
        if (!canceled) setUrl(nextUrl)
      })
      .catch(() => {
        if (!canceled) setUrl('')
      })
    return () => {
      canceled = true
    }
  }, [storageKey])
  return url
}

type SecureAttachmentImageProps = ImgHTMLAttributes<HTMLImageElement> & {
  storageKey: string
}

export function SecureAttachmentImage({ storageKey, ...imgProps }: SecureAttachmentImageProps) {
  const url = useResolvedAttachmentUrl(storageKey)
  if (!url) return null
  return <img src={url} {...imgProps} />
}

type SecureAttachmentLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  storageKey: string
  children: ReactNode
}

export function SecureAttachmentLink({ storageKey, children, ...anchorProps }: SecureAttachmentLinkProps) {
  const url = useResolvedAttachmentUrl(storageKey)
  if (!url) return <>{children}</>
  return (
    <a href={url} {...anchorProps}>
      {children}
    </a>
  )
}
