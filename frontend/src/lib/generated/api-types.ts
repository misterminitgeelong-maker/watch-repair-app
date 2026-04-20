/**
 * Curated exports from OpenAPI-generated types (`openapi.d.ts`).
 * Regenerate with `npm run generate:api-types` after backend API changes.
 */
import type { components, operations } from './openapi'

export type OpenApiAutoKeyJobRead = components['schemas']['AutoKeyJobRead']

export type ListAutoKeyJobsResponse =
  operations['list_auto_key_jobs_v1_auto_key_jobs_get']['responses'][200]['content']['application/json']
