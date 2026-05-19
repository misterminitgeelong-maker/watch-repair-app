/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type Theme = 'warm' | 'neutral' | 'dark' | 'minit'

const STORAGE_KEY = 'ms-theme'

export const THEME_PERSISTED_EVENT = 'ms-theme-persisted'

export function readStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'warm'
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (raw === 'warm' || raw === 'neutral' || raw === 'dark' || raw === 'minit') return raw
  return 'warm'
}

export function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return
  if (theme === 'warm') {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
}

/** Apply theme to DOM, localStorage, and sync ThemeProvider state (via custom event). */
export function persistTheme(theme: Theme) {
  applyTheme(theme)
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* storage unavailable */
  }
  window.dispatchEvent(new CustomEvent(THEME_PERSISTED_EVENT, { detail: { theme } }))
}

interface ThemeCtx {
  theme: Theme
  setTheme: (next: Theme) => void
}

const ThemeContext = createContext<ThemeCtx | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => readStoredTheme())

  useEffect(() => {
    applyTheme(theme)
    try {
      window.localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      /* storage unavailable */
    }
  }, [theme])

  useEffect(() => {
    function onThemePersisted(e: Event) {
      const next = (e as CustomEvent<{ theme: Theme }>).detail?.theme
      if (next === 'warm' || next === 'neutral' || next === 'dark' || next === 'minit') {
        setThemeState(next)
      }
    }
    window.addEventListener(THEME_PERSISTED_EVENT, onThemePersisted)
    return () => window.removeEventListener(THEME_PERSISTED_EVENT, onThemePersisted)
  }, [])

  const value: ThemeCtx = {
    theme,
    setTheme: (next) => setThemeState(next),
  }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
