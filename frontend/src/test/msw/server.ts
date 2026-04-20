import { setupServer } from 'msw/node'
import { autoKeyJobsHandlers } from './handlers'

export const testServer = setupServer(...autoKeyJobsHandlers)
