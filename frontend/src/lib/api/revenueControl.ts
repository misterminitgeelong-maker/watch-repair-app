import api from './client'
import type { components } from '../generated/openapi'

export type RevenueItem = components['schemas']['RevenueItem']
export type RevenueResponse = components['schemas']['RevenueResponse']
export type FollowUpUpdate = components['schemas']['FollowUpUpdate']
export type RevenueKind = RevenueItem['kind']
export interface RevenueFilters {
  kind?: RevenueKind
  state: 'due' | 'scheduled' | 'all'
  owner?: string
  search: string
  offset: number
}
export const getRevenueControl = (params: RevenueFilters) => api.get<RevenueResponse>('/revenue-control', { params })
export const saveRevenueFollowUp = (key: string, body: FollowUpUpdate) =>
  api.put<RevenueItem>(`/revenue-control/${encodeURIComponent(key)}/follow-up`, body)
