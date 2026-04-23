/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type Theme = 'warm' | 'neutral' | 'dark' | 'minit'

const STORAGE_KEY = 'ms-theme'

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
