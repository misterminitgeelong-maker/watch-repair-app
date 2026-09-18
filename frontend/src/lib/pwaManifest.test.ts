/** Guards the PWA install contract: a broken manifest silently un-installs the app. */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const publicDir = resolve(__dirname, '../../public')
const readPublic = (name: string) => readFileSync(resolve(publicDir, name), 'utf8')

const manifest = JSON.parse(readPublic('manifest.json')) as {
  id: string
  name: string
  short_name: string
  start_url: string
  scope: string
  display: string
  theme_color: string
  background_color: string
  icons: Array<{ src: string; sizes: string; type: string; purpose: string }>
  shortcuts?: Array<{ name: string; url: string }>
}
const indexHtml = readPublic('../index.html')
const sw = readPublic('sw.js')
const mainSource = readPublic('../src/main.tsx')

describe('manifest.json', () => {
  it('declares what browsers require to offer installation', () => {
    expect(manifest.name).toBeTruthy()
    expect(manifest.short_name.length).toBeLessThanOrEqual(12)
    expect(manifest.id).toBeTruthy()
    expect(manifest.scope).toBe('/')
    expect(manifest.display).toBe('standalone')
    expect(manifest.start_url.startsWith('/')).toBe(true)
  })

  it('ships both a 192 and a 512 PNG, the sizes Chrome checks for', () => {
    const pngs = manifest.icons.filter(i => i.type === 'image/png')
    expect(pngs.some(i => i.sizes === '192x192')).toBe(true)
    expect(pngs.some(i => i.sizes === '512x512')).toBe(true)
  })

  it('uses dedicated safe-zone icons for maskable, not the same art as "any"', () => {
    const maskable = manifest.icons.filter(i => i.purpose === 'maskable')
    const any = manifest.icons.filter(i => i.purpose === 'any')
    expect(maskable.length).toBeGreaterThanOrEqual(2)
    for (const icon of maskable) {
      expect(any.some(a => a.src === icon.src)).toBe(false)
    }
  })

  it('points every icon and shortcut at a file that exists', () => {
    for (const icon of manifest.icons) {
      expect(() => readPublic(icon.src.replace(/^\//, ''))).not.toThrow()
    }
    for (const shortcut of manifest.shortcuts ?? []) {
      expect(shortcut.url.startsWith('/')).toBe(true)
    }
  })

  it('agrees with index.html on theme colour', () => {
    const meta = indexHtml.match(/<meta\s+name="theme-color"\s+content="([^"]+)"/i)
    expect(meta?.[1]?.toUpperCase()).toBe(manifest.theme_color.toUpperCase())
    expect(manifest.background_color).toMatch(/^#[0-9A-Fa-f]{6}$/)
  })
})

describe('index.html', () => {
  it('opts into safe-area handling for notched phones', () => {
    expect(indexHtml).toMatch(/name="viewport"[^>]*viewport-fit=cover/)
  })

  it('carries iOS home-screen metadata and a 180x180 touch icon', () => {
    expect(indexHtml).toMatch(/name="apple-mobile-web-app-capable"\s+content="yes"/)
    expect(indexHtml).toMatch(/name="mobile-web-app-capable"\s+content="yes"/)
    expect(indexHtml).toMatch(/name="apple-mobile-web-app-title"/)
    expect(indexHtml).toMatch(/rel="apple-touch-icon"[^>]*sizes="180x180"/)
  })

  it('links the manifest', () => {
    expect(indexHtml).toMatch(/rel="manifest"\s+href="\/manifest\.json"/)
  })
})

describe('sw.js', () => {
  it('precaches the offline shell, including the icons the manifest names', () => {
    expect(sw).toContain("'/index.html'")
    expect(sw).toContain("'/offline.html'")
    expect(sw).toContain("'/manifest.json'")
    for (const icon of manifest.icons.filter(i => i.type === 'image/png')) {
      expect(sw).toContain(`'${icon.src}'`)
    }
  })

  it('keeps API responses out of the cache', () => {
    expect(sw).toMatch(/url\.pathname\.startsWith\('\/v1\/'\)/)
    // The /v1/ branch returns before any cache.put.
    const apiBranch = sw.slice(sw.indexOf("startsWith('/v1/')"), sw.indexOf('HTML navigations'))
    expect(apiBranch).not.toContain('cache.put')
  })

  it('keeps the versioned-cache update strategy', () => {
    expect(sw).toMatch(/const CACHE_VERSION = '[^']+'/)
    expect(sw).toContain('skipWaiting')
    expect(sw).toContain('clients.claim')
    // Old versioned caches are swept on activate.
    expect(sw).toContain('caches.delete')
  })
})

describe('service worker registration', () => {
  it('cache-busts the worker script with the deployment build id', () => {
    expect(mainSource).toContain('VITE_APP_BUILD_ID')
    expect(mainSource).toMatch(/`\/sw\.js\?v=\$\{encodeURIComponent/)
  })
})
