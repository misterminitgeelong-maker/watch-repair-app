import { describe, expect, it } from 'vitest'
import {
  AUTO_KEY_MOBILE_LANDING_HREF,
  applyAutoKeyUrl,
  defaultAutoKeyJobsLayout,
  isPosDestinationUrl,
  persistableAutoKeySavedView,
  resolveAutoKeyLanding,
} from './landingView'

describe('defaultAutoKeyJobsLayout', () => {
  it('is Kanban on phone and Today on desktop', () => {
    expect(defaultAutoKeyJobsLayout(true)).toBe('board')
    expect(defaultAutoKeyJobsLayout(false)).toBe('today')
  })
})

describe('resolveAutoKeyLanding', () => {
  it('defaults phone to Kanban and desktop to Today', () => {
    expect(resolveAutoKeyLanding({
      urlView: null, urlJobsLayout: null, urlJobId: null, isMobile: true,
    })).toEqual({ view: 'jobs', jobsLayout: 'board' })
    expect(resolveAutoKeyLanding({
      urlView: null, urlJobsLayout: null, urlJobId: null, isMobile: false,
    })).toEqual({ view: 'jobs', jobsLayout: 'today' })
  })

  it('ignores leftover POS with no job_id, including saved last-view=pos', () => {
    expect(resolveAutoKeyLanding({
      urlView: 'pos', urlJobsLayout: null, urlJobId: null, isMobile: true,
      saved: { view: 'pos', jobsLayout: 'today' },
    })).toEqual({ view: 'jobs', jobsLayout: 'board' })
    expect(resolveAutoKeyLanding({
      urlView: null, urlJobsLayout: null, urlJobId: null, isMobile: false,
      saved: { view: 'pos' },
    })).toEqual({ view: 'jobs', jobsLayout: 'today' })
  })

  it('keeps POS when a job is on the URL (New Quote)', () => {
    expect(isPosDestinationUrl('pos', 'job-1')).toBe(true)
    expect(resolveAutoKeyLanding({
      urlView: 'pos', urlJobsLayout: null, urlJobId: 'job-1', isMobile: true,
    })).toEqual({ view: 'pos', jobsLayout: 'board' })
  })

  it('honours an explicit Kanban / List URL and non-POS last-view', () => {
    expect(resolveAutoKeyLanding({
      urlView: null, urlJobsLayout: 'board', urlJobId: null, isMobile: false,
    })).toEqual({ view: 'jobs', jobsLayout: 'board' })
    expect(resolveAutoKeyLanding({
      urlView: 'jobs', urlJobsLayout: 'list', urlJobId: null, isMobile: true,
    })).toEqual({ view: 'jobs', jobsLayout: 'list' })
    expect(resolveAutoKeyLanding({
      urlView: null, urlJobsLayout: null, urlJobId: null, isMobile: true,
      saved: { view: 'map' },
    })).toEqual({ view: 'map', jobsLayout: 'board' })
    expect(resolveAutoKeyLanding({
      urlView: null, urlJobsLayout: null, urlJobId: null, isMobile: false,
      saved: { view: 'jobs', jobsLayout: 'list' },
    })).toEqual({ view: 'jobs', jobsLayout: 'list' })
  })
})

describe('applyAutoKeyUrl', () => {
  it('follows the Mobile tab onto Kanban and keeps a chosen POS till', () => {
    expect(AUTO_KEY_MOBILE_LANDING_HREF).toBe('/auto-key?jobs_layout=board')
    expect(applyAutoKeyUrl({
      urlView: null, urlJobsLayout: 'board', urlJobId: null, isMobile: true,
    })).toEqual({ view: 'jobs', jobsLayout: 'board' })
    expect(applyAutoKeyUrl({
      urlView: 'pos', urlJobsLayout: null, urlJobId: null, isMobile: true,
    })).toEqual({ view: 'pos', jobsLayout: 'board' })
  })
})

describe('persistableAutoKeySavedView', () => {
  it('stores jobs instead of POS so the next landing is not an empty till', () => {
    expect(persistableAutoKeySavedView({ view: 'pos', jobsLayout: 'board' })).toEqual({
      view: 'jobs',
      jobsLayout: 'board',
    })
    expect(persistableAutoKeySavedView({ view: 'map' })).toEqual({ view: 'map' })
  })
})
