/**
 * Render a routed page under the providers it expects, for page-level tests.
 *
 * The job-detail pages are 1,100-1,600 lines each and had no tests at all. They
 * need a router (they read :id from the path), a QueryClient, and the toast and
 * theme providers. AuthContext is mocked per test rather than provided, so a
 * test can say "this user has the auto_key feature" without a login round trip.
 */
import type { ReactElement, ReactNode } from 'react'
import { Suspense } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { render } from '@testing-library/react'

import { ThemeProvider } from '@/context/ThemeContext'
import { ToastProvider } from '@/lib/toast'

/** Retries turn a deliberate 500 into a multi-second wait, so switch them off. */
export function makeTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

export function renderAtRoute(
  ui: ReactElement,
  { path, route }: { path: string; route: string },
  wrapper?: (children: ReactNode) => ReactNode,
) {
  const client = makeTestQueryClient()
  const tree = (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[route]}>
            <Suspense fallback={<div>loading route</div>}>
              <Routes>
                <Route path={path} element={ui} />
                {/* Anything the page navigates to lands here rather than erroring. */}
                <Route path="*" element={<div>elsewhere</div>} />
              </Routes>
            </Suspense>
          </MemoryRouter>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
  return render(<>{wrapper ? wrapper(tree) : tree}</>)
}
