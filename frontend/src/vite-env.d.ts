/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_MAPS_API_KEY?: string
  /** Optional API origin for native builds, e.g. `https://mainspring.au` */
  readonly VITE_API_BASE_URL?: string
  /** Comma-separated hostnames for Universal Link in-app routing (native); default mainspring.au + www */
  readonly VITE_UNIVERSAL_LINK_HOSTS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
