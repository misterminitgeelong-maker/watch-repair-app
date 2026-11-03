import api from './client'

export interface MessagingNetwork {
  id: string; name: string; own_state: string | null; allowed_states: string[]
  can_publish_network: boolean; publish_states: string[]; can_post: boolean
}
export interface StateHub {
  code: string; name: string; mine: boolean; accessible: boolean; can_post: boolean; unread: number
}
export interface ChatAttachment { id: string; filename: string; content_type: string; size_bytes: number }
export interface HubMessage {
  attachments: ChatAttachment[]
  id: string; body: string; created_at: string; sender_name: string; shop_name: string; mine: boolean
  kind: 'message' | 'stock_request'; resolved_at: string | null; pinned: boolean
  reply_to_id: string | null; reply_preview: string | null; can_moderate?: boolean
}
export interface HubPage { messages: HubMessage[]; has_more: boolean; next_before: string | null }
export interface Announcement {
  id: string; title: string; body: string; state_code: string | null
  category: 'update' | 'training' | 'important'; pinned: boolean; requires_confirmation: boolean
  created_at: string; author_name: string; read: boolean; confirmed: boolean
}
export interface AnnouncementDraft {
  title: string; body: string; state_code: string | null; category: Announcement['category']
  pinned: boolean; requires_confirmation: boolean
}
const root = (network: string) => `/network-community/${network}`
export const messagingNetworks = () => api.get<MessagingNetwork[]>('/network-community/networks').then(r => r.data)
export const stateHubs = (network: string) => api.get<StateHub[]>(`${root(network)}/hubs`).then(r => r.data)
export const hubMessages = (network: string, code: string, before?: string) =>
  api.get<HubPage>(`${root(network)}/hubs/${code}/messages`, { params: before ? { before } : {} }).then(r => r.data)
export const sendHubMessage = (network: string, code: string, data: { body: string; kind: string; reply_to_id?: string }) =>
  api.post<HubMessage>(`${root(network)}/hubs/${code}/messages`, data).then(r => r.data)
export const updateHubMessage = (network: string, code: string, id: string, data: { pinned?: boolean; resolved?: boolean }) =>
  api.patch<HubMessage>(`${root(network)}/hubs/${code}/messages/${id}`, data).then(r => r.data)
export const readHub = (network: string, code: string, message_id: string) =>
  api.post(`${root(network)}/hubs/${code}/read`, { message_id })
export const listAnnouncements = (network: string, offset = 0) =>
  api.get<{ announcements: Announcement[]; has_more: boolean }>(`${root(network)}/announcements`, { params: { offset } }).then(r => r.data)
export const publishAnnouncement = (network: string, data: AnnouncementDraft) =>
  api.post<Announcement>(`${root(network)}/announcements`, data).then(r => r.data)
export const acknowledgeAnnouncement = (network: string, id: string, confirm = false) =>
  api.post<Announcement>(`${root(network)}/announcements/${id}/receipt`, { confirm }).then(r => r.data)


export const sendHubPost = (network: string, code: string, data: { body: string; kind: string; reply_to_id?: string }, files: File[]) => {
  const form = new FormData()
  form.set('body', data.body)
  form.set('kind', data.kind)
  if (data.reply_to_id) form.set('reply_to_id', data.reply_to_id)
  files.forEach(file => form.append('files', file))
  return api.post<HubMessage>(`${root(network)}/hubs/${code}/posts`, form).then(r => r.data)
}
export const sendDirectPost = (network: string, tenant: string, body: string, files: File[]) => {
  const form = new FormData()
  form.set('body', body)
  files.forEach(file => form.append('files', file))
  return api.post<{ conversation_id: string }>(`${root(network)}/direct/${tenant}/posts`, form).then(r => r.data)
}
