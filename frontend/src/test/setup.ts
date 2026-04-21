import { afterAll, afterEach, beforeAll } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { testServer } from './msw/server'

const memoryStorage = (): Storage => {
  let store: Record<string, string> = {}
  return {
    get length() {
      return Object.keys(store).length
    },
    clear() {
      store = {}
    },
    getItem(key: string) {
      return store[key] ?? null
    },
    key(index: number) {
      return Object.keys(store)[index] ?? null
    },
    removeItem(key: string) {
      delete store[key]
    },
    setItem(key: string, value: string) {
      store[key] = value
    },
  } as Storage
}

beforeAll(() => {
  const mem = memoryStorage()
  Object.defineProperty(globalThis, 'localStorage', { value: mem, writable: true })
  Object.defineProperty(globalThis, 'sessionStorage', { value: memoryStorage(), writable: true })
  testServer.listen({ onUnhandledRequest: 'error' })
})

afterEach(() => {
  testServer.resetHandlers()
  // Tear down rendered React trees between component tests so subsequent
  // screen.getByRole() queries don't see stale dialogs/backdrops.
  cleanup()
})

afterAll(() => {
  testServer.close()
})
