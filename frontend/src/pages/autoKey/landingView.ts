import type { AutoKeySavedView } from '@/lib/savedViews'

export type AutoKeyPageView = 'jobs' | 'pos' | 'dispatch' | 'week' | 'map' | 'planner' | 'reports'
export type AutoKeyJobsLayout = 'today' | 'board' | 'list'

export const AUTO_KEY_PAGE_VIEWS = [
  'jobs',
  'pos',
  'dispatch',
  'week',
  'map',
  'planner',
  'reports',
] as const

/** Phone Mobile tab: Kanban, not POS and not Today. */
export const AUTO_KEY_MOBILE_LANDING_HREF = '/auto-key?jobs_layout=board'

export interface AutoKeyLanding {
  view: AutoKeyPageView
  jobsLayout: AutoKeyJobsLayout
}

export function isAutoKeyPageView(value: string | null | undefined): value is AutoKeyPageView {
  return !!value && (AUTO_KEY_PAGE_VIEWS as readonly string[]).includes(value)
}

export function parseAutoKeyJobsLayout(value: string | null | undefined): AutoKeyJobsLayout | null {
  if (value === 'today' || value === 'board' || value === 'list') return value
  return null
}

export function defaultAutoKeyJobsLayout(isMobile: boolean): AutoKeyJobsLayout {
  return isMobile ? 'board' : 'today'
}

/** POS is a destination (New Quote / till on a job), not a landing view. */
export function isPosDestinationUrl(urlView: string | null | undefined, urlJobId: string | null | undefined): boolean {
  return urlView === 'pos' && Boolean(urlJobId)
}

function savedPageView(saved: AutoKeySavedView | undefined): AutoKeyPageView | null {
  if (!saved?.view || saved.view === 'pos' || !isAutoKeyPageView(saved.view)) return null
  return saved.view
}

/**
 * First paint for `/auto-key`.
 * Phone default is Kanban. Desktop default stays Today.
 * `?view=pos` without a job is leftover last-view / empty till — ignore it.
 */
export function resolveAutoKeyLanding(opts: {
  urlView: string | null
  urlJobsLayout: string | null
  urlJobId: string | null
  saved?: AutoKeySavedView
  isMobile: boolean
}): AutoKeyLanding {
  const fallbackLayout = defaultAutoKeyJobsLayout(opts.isMobile)
  const urlLayout = parseAutoKeyJobsLayout(opts.urlJobsLayout)

  if (isPosDestinationUrl(opts.urlView, opts.urlJobId)) {
    return { view: 'pos', jobsLayout: urlLayout ?? fallbackLayout }
  }

  if (opts.urlView && isAutoKeyPageView(opts.urlView) && opts.urlView !== 'pos') {
    return {
      view: opts.urlView,
      jobsLayout: opts.urlView === 'jobs' ? (urlLayout ?? parseAutoKeyJobsLayout(opts.saved?.jobsLayout) ?? fallbackLayout) : fallbackLayout,
    }
  }

  if (urlLayout) {
    return { view: 'jobs', jobsLayout: urlLayout }
  }

  const savedView = savedPageView(opts.saved)
  const savedLayout = parseAutoKeyJobsLayout(opts.saved?.jobsLayout)
  if (savedView) {
    return {
      view: savedView,
      jobsLayout: savedView === 'jobs' ? (savedLayout ?? fallbackLayout) : fallbackLayout,
    }
  }
  // A leftover POS last-view should not keep its jobsLayout (often Today).
  if (savedLayout && opts.saved?.view !== 'pos') {
    return { view: 'jobs', jobsLayout: savedLayout }
  }

  return { view: 'jobs', jobsLayout: fallbackLayout }
}

/** Follow an in-app URL change (tab, New Quote). POS without a job is valid here. */
export function applyAutoKeyUrl(opts: {
  urlView: string | null
  urlJobsLayout: string | null
  urlJobId: string | null
  isMobile: boolean
}): AutoKeyLanding {
  if (opts.urlView === 'pos') {
    return { view: 'pos', jobsLayout: defaultAutoKeyJobsLayout(opts.isMobile) }
  }
  return resolveAutoKeyLanding({ ...opts, saved: {} })
}

/** Never store POS as the next landing view. */
export function persistableAutoKeySavedView(value: AutoKeySavedView): AutoKeySavedView {
  if (value.view === 'pos') {
    return { ...value, view: 'jobs' }
  }
  return value
}
