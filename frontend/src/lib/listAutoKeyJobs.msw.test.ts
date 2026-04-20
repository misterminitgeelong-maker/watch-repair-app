import { describe, it, expect, beforeEach, beforeAll, afterAll } from 'vitest'
import api, { listAutoKeyJobs } from './api'
import { testServer } from '@/test/msw/server'
import { autoKeyJobsHandlersWith, makeMockAutoKeyJob } from '@/test/msw/handlers'

describe('listAutoKeyJobs with MSW', () => {
  const previousBase = api.defaults.baseURL

  beforeAll(() => {
    // Node axios cannot resolve relative `/v1`; use absolute origin so MSW can intercept.
    api.defaults.baseURL = 'http://127.0.0.1/v1'
  })

  afterAll(() => {
    api.defaults.baseURL = previousBase
  })

  beforeEach(() => {
    testServer.resetHandlers()
  })

  it('returns empty array when API has no jobs', async () => {
    const { data } = await listAutoKeyJobs()
    expect(data).toEqual([])
  })

  it('returns mocked jobs when handlers supply rows', async () => {
    const job = makeMockAutoKeyJob({ job_number: 'AK-777', title: 'Keyed response' })
    testServer.use(...autoKeyJobsHandlersWith([job]))
    const { data } = await listAutoKeyJobs()
    expect(data).toHaveLength(1)
    expect(data[0]?.job_number).toBe('AK-777')
    expect(data[0]?.title).toBe('Keyed response')
  })
})
