import { useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { ArrowLeft, Check, CheckCheck, Hash, Info, LockKeyhole, Megaphone, MessageSquare, Pin, Reply, Search, Send, Users } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import api, { getApiErrorMessage, type NetworkContact, type NetworkConversation, type NetworkMessage } from '@/lib/api'
import {
  acknowledgeAnnouncement, hubMessages, listAnnouncements, messagingNetworks, publishAnnouncement,
  readHub, sendHubPost, sendDirectPost, stateHubs, updateHubMessage,
  type AnnouncementDraft, type ChatAttachment, type HubMessage, type MessagingNetwork, type StateHub,
} from '@/lib/api/networkCommunity'
import './networkMessaging.css'

const stateNames: Record<string, string> = { VIC: 'Victoria', NSW: 'New South Wales', QLD: 'Queensland', WA: 'Western Australia', SA: 'South Australia', TAS: 'Tasmania', ACT: 'Australian Capital Territory', NT: 'Northern Territory', NZ: 'New Zealand' }
const when = (value: string) => new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z').toLocaleString('en-AU', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
const initials = (value: string) => value.split(/\s+/).filter(Boolean).slice(0, 2).map(s => s[0]).join('').toUpperCase()
function ErrorNotice({ error }: { error: unknown }) {
  return error ? <p role="alert" className="nc-error">{getApiErrorMessage(error, 'Could not load messaging. Please try again.')}</p> : null
}
function Badge({ count }: { count: number }) { return count > 0 ? <span className="nc-count">{count > 99 ? '99+' : count}</span> : null }

function FilePicker({ files, setFiles, disabled }: { files: File[]; setFiles: (files: File[]) => void; disabled: boolean }) {
  const [error, setError] = useState('')
  function add(list: FileList | null) {
    const next = [...files, ...Array.from(list ?? [])]
    if (next.length > 5 || next.some(f => f.size > 5 * 1024 * 1024) || next.reduce((sum, f) => sum + f.size, 0) > 10 * 1024 * 1024) {
      setError('Attach up to five files, 5 MB each and 10 MB total.'); return
    }
    setError(''); setFiles(next)
  }
  return <div className="nc-file-picker">
    <div className="nc-inline-actions">
      <label className="nc-file-control">Photo<input className="nc-sr-only" type="file" aria-label="Attach photo" accept="image/png,image/jpeg,image/webp" capture="environment" disabled={disabled} onChange={e => { add(e.target.files); e.target.value = '' }} /></label>
      <label className="nc-file-control">Attach file<input className="nc-sr-only" type="file" aria-label="Attach file" multiple accept="image/png,image/jpeg,image/webp,application/pdf" disabled={disabled} onChange={e => { add(e.target.files); e.target.value = '' }} /></label>
      <span className="nc-muted">Photos or PDFs · 5 MB per file</span>
    </div>
    {files.map((file, i) => <div className="nc-selected-file" key={file.name + i}><span>{file.name}</span><button type="button" disabled={disabled} onClick={() => setFiles(files.filter((_, index) => index !== i))} aria-label={'Remove ' + file.name}>Remove</button></div>)}
    {error && <p role="alert" className="nc-error">{error}</p>}
  </div>
}

function MessageFiles({ attachments }: { attachments: ChatAttachment[] }) {
  const download = useMutation({ mutationFn: async (file: ChatAttachment) => {
    const data = await api.get<Blob>(`/network-community/attachments/${file.id}`, { responseType: 'blob' }).then(r => r.data)
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url; a.download = file.filename; document.body.appendChild(a); a.click(); a.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } })
  return <>{attachments.map(file => <button key={file.id} type="button" className="nc-download" disabled={download.isPending} onClick={() => download.mutate(file)}>{file.filename} · {Math.ceil(file.size_bytes / 1024)} KB ↓</button>)}<ErrorNotice error={download.error} /></>
}


export default function NetworkMessagingPage() {
  const { tenantId } = useAuth()
  const [params, setParams] = useSearchParams()
  const networkQuery = useQuery({ queryKey: ['community-networks', tenantId], queryFn: messagingNetworks })
  const networks = networkQuery.data ?? []
  const deepLink = useQuery({
    queryKey: ['network-conversation-link', tenantId, params.get('c')],
    queryFn: () => api.get<NetworkConversation[]>('/network-messages/conversations').then(r => r.data),
    enabled: !!params.get('c') && !params.get('network'),
  })
  const linkedNetwork = deepLink.data?.find(c => c.id === params.get('c'))?.parent_account_id
  const network = networks.find(n => n.id === (params.get('network') ?? linkedNetwork)) ?? networks[0]
  const tab = ['directory', 'announcements', 'hubs'].includes(params.get('tab') ?? '') ? params.get('tab')! : 'chats'
  const convId = params.get('c')
  const newTo = params.get('to')
  const hubQuery = useQuery({ queryKey: ['state-hubs', tenantId, network?.id], queryFn: () => stateHubs(network!.id), enabled: !!network, refetchInterval: 30_000 })
  const hubs = hubQuery.data ?? []
  const selectedHub = hubs.find(h => h.code === params.get('hub') && h.accessible)
    ?? (!convId && !newTo ? hubs.find(h => h.mine && h.accessible) : undefined)
  const conversations = useQuery({
    queryKey: ['network-conversations', tenantId, network?.id],
    queryFn: () => api.get<NetworkConversation[]>('/network-messages/conversations', { params: { parent_account_id: network!.id } }).then(r => r.data),
    enabled: !!network, refetchInterval: 15_000,
  })
  const contacts = useQuery({
    queryKey: ['network-contacts', tenantId, network?.id],
    queryFn: () => api.get<DirectoryContact[]>('/network-messages/contacts', { params: { parent_account_id: network!.id } }).then(r => r.data),
    enabled: !!network,
  })
  const current = conversations.data?.find(c => c.id === convId)
  function navigate(values: Record<string, string>) {
    setParams({ ...(network ? { network: network.id } : {}), ...values })
  }
  const [chatSearch, setChatSearch] = useState('')
  return <div className="nc-page">
    <header className="nc-page-header"><div><h1>Messages</h1><p>Your state first. The whole Minit network within reach.</p></div>
      {networks.length > 1 && <label>Network<select value={network?.id ?? ''} onChange={e => setParams({ network: e.target.value })}>{networks.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>}
    </header>
    <ErrorNotice error={networkQuery.error} />
    {networkQuery.isPending ? <p role="status">Loading your network…</p> : !network ? <section className="nc-empty"><Users /><h2>Your network is not connected yet</h2><p>Ask Support Office to check your shop’s network membership. No shop data or access permissions are changed by messaging.</p></section> : <>
      <nav className="nc-tabs" aria-label="Messaging">
        {([['chats', 'Chats', MessageSquare], ['directory', 'Shop directory', Users], ['announcements', 'Announcements', Megaphone], ['hubs', 'State hubs', Hash]] as const).map(([value, label, Icon]) => <button type="button" key={value} aria-current={tab === value ? 'page' : undefined} onClick={() => navigate({ tab: value })}><Icon size={16} />{label}</button>)}
      </nav>
      <ErrorNotice error={hubQuery.error} />
      {tab === 'hubs' && <section>
        <div className="nc-state-hero"><div><span className="nc-eyebrow">YOUR SHOP’S HUB</span><h2>{network.own_state ? stateNames[network.own_state] : 'Choose a state hub'}</h2><p>{network.own_state ? 'Share stock, ask for advice and catch up with shops in your state.' : 'HQ and state managers can open the hubs available to their role.'}</p></div>
          {hubs.find(h => h.mine && h.accessible) && <button className="nc-button" onClick={() => navigate({ hub: network.own_state! })}>Open my state hub</button>}</div>
        <h2>Around the network</h2><p className="nc-muted">Each state has its own conversation. Shops join their assigned state automatically.</p>
        <div className="nc-hub-grid">{hubs.map(h => <button key={h.code} className={'nc-hub-card nc-state-' + h.code} disabled={!h.accessible} onClick={() => navigate({ hub: h.code })}>
          <span className="nc-state-tag">{h.code}</span><strong>{h.name}</strong><span>{h.mine ? 'Your hub' : h.accessible ? 'Open state hub' : 'For shops in this state'} {h.accessible ? <Badge count={h.unread} /> : <LockKeyhole size={13} />}</span>
        </button>)}</div><p className="nc-muted">Need someone interstate? Find any participating shop in the Shop directory.</p>
      </section>}
      {tab === 'directory' && <Directory contacts={contacts.data ?? []} error={contacts.error} loading={contacts.isPending} ownState={network.own_state} onMessage={id => navigate({ to: id })} />}
      {tab === 'announcements' && <Announcements key={network.id} network={network} onHub={code => navigate({ hub: code })} />}
      {tab === 'chats' && <div className={'nc-chat-layout' + (convId || newTo || params.get('hub') ? ' nc-thread-open' : '')}>
        <aside className="nc-conversations"><label className="nc-search"><Search size={16} /><input aria-label="Search conversations" placeholder="Search conversations…" value={chatSearch} onChange={e => setChatSearch(e.target.value)} /></label>
          <h2>MY STATE HUB</h2>{hubs.filter(h => h.accessible && h.name.toLowerCase().includes(chatSearch.toLowerCase())).map(h => <button key={h.code} className={'nc-chat-row nc-state-' + h.code + (selectedHub?.code === h.code && !convId && !newTo ? ' selected' : '')} onClick={() => navigate({ hub: h.code })}>
            <span className="nc-avatar"><Hash size={15} /></span><span className="nc-row-copy"><strong>{h.name}</strong><small>Stock, advice and local updates</small></span><Badge count={h.unread} />
          </button>)}
          {!hubs.some(h => h.accessible) && <p className="nc-help">Your shop needs a state assignment to join a hub. You can still message other shops.</p>}
          <h2>DIRECT MESSAGES</h2><ErrorNotice error={conversations.error} />
          {conversations.isPending && <p className="nc-help">Loading conversations…</p>}
          {(conversations.data ?? []).filter(c => c.other_name.toLowerCase().includes(chatSearch.toLowerCase())).map(c => <button key={c.id} className={'nc-chat-row' + (convId === c.id ? ' selected' : '')} onClick={() => navigate({ c: c.id })}>
            <span className="nc-avatar">{initials(c.other_name)}</span><span className="nc-row-copy"><strong>{c.other_name}</strong><small>{c.last_body}</small><small>{when(c.last_message_at)}</small></span><Badge count={c.unread} />
          </button>)}
          {!conversations.data?.length && <p className="nc-help">No direct conversations yet.</p>}
          <div className="nc-help"><strong>Need another shop?</strong><p>Search signed-up shops in any state.</p><button className="nc-button" onClick={() => navigate({ tab: 'directory' })}>Browse all shops</button></div>
        </aside>
        <section className="nc-thread"><button className="nc-back" onClick={() => navigate({ tab: 'chats' })}><ArrowLeft size={16} />All conversations</button>
          {convId || newTo ? <DirectThread networkId={network.id} key={convId ?? newTo} conversation={current} conversationId={convId} recipient={current?.other_tenant_id ?? newTo} recipientName={current?.other_name ?? contacts.data?.find(c => c.tenant_id === newTo)?.name} onSent={id => navigate({ c: id })} />
            : selectedHub ? <HubThread key={network.id + selectedHub.code} network={network} hub={selectedHub} />
            : <div className="nc-empty"><MessageSquare /><h2>Start a conversation</h2><p>Choose your state hub or find a shop in the directory.</p></div>}
        </section>
      </div>}
    </>}
  </div>
}

interface DirectoryContact extends NetworkContact { state_code: string | null; shop_number: string | null }
function Directory({ contacts, ownState, onMessage, error, loading }: { contacts: DirectoryContact[]; ownState: string | null; onMessage: (id: string) => void; error: unknown; loading: boolean }) {
  const [q, setQ] = useState('')
  const [state, setState] = useState('all')
  const [role, setRole] = useState('all')
  const filtered = contacts.filter(c => (state === 'all' || c.state_code === state) && (role === 'all' || c.network_role === role) && (c.name + ' ' + (c.shop_number ?? '') + ' ' + (stateNames[c.state_code ?? ''] ?? '')).toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => Number(b.state_code === ownState) - Number(a.state_code === ownState) || a.name.localeCompare(b.name))
  return <section><div className="nc-directory-filters"><label className="nc-search"><Search size={16} /><input aria-label="Search shops" placeholder="Search shop name, number or location…" value={q} onChange={e => setQ(e.target.value)} /></label>
    <label>State<select value={state} onChange={e => setState(e.target.value)}><option value="all">All states</option>{Object.entries(stateNames).map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select></label>
    <label>Site type<select value={role} onChange={e => setRole(e.target.value)}><option value="all">All sites</option><option value="retail">Retail shops</option><option value="operator">Mobile operators</option><option value="hq">Support Office</option></select></label></div>
    <ErrorNotice error={error} /><p className="nc-eyebrow">{loading ? 'Loading shops…' : filtered.length + ' PARTICIPATING SITES'} · Your state shown first</p>
    <div className="nc-directory">{filtered.map(c => <div key={c.tenant_id} className={'nc-shop-row nc-state-' + c.state_code}><span className="nc-state-tag">{stateNames[c.state_code ?? ''] ?? 'Unassigned'}</span><strong>{c.name}</strong><span className="nc-muted">{c.network_role === 'hq' ? 'Support Office' : c.network_role === 'operator' ? 'Mobile operator' : 'Retail shop'}</span><button className="nc-button" onClick={() => onMessage(c.tenant_id)}>Message shop</button></div>)}</div>
    {!loading && !filtered.length && <p className="nc-empty">No signed-up sites match these filters.</p>}
  </section>
}

function HubThread({ network, hub }: { network: MessagingNetwork; hub: StateHub }) {
  const qc = useQueryClient()
  const { tenantId } = useAuth()
  const [draft, setDraft] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [reply, setReply] = useState<HubMessage | null>(null)
  const [kind, setKind] = useState('message')
  const [info, setInfo] = useState(false)
  const [pinnedOnly, setPinnedOnly] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)
  const key = ['state-thread', tenantId, network.id, hub.code]
  const messages = useInfiniteQuery({ queryKey: key, initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => hubMessages(network.id, hub.code, pageParam),
    getNextPageParam: page => page.next_before ?? undefined, refetchInterval: 15_000 })
  const rows = [...(messages.data?.pages ?? [])].reverse().flatMap(p => p.messages)
  const latest = messages.data?.pages[0]?.messages.at(-1)?.id
  const read = useMutation({ mutationFn: (id: string) => readHub(network.id, hub.code, id), onSuccess: () => { void qc.invalidateQueries({ queryKey: ['state-hubs'] }) } })
  const markRead = read.mutate
  useEffect(() => {
    if (!latest || document.visibilityState !== 'visible') return
    markRead(latest)
  }, [latest, markRead])
  useEffect(() => {
    const onVisible = () => { if (latest && document.visibilityState === 'visible') markRead(latest) }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [latest, markRead])
  useEffect(() => { bottom.current?.scrollIntoView?.({ block: 'nearest' }) }, [latest])
  const send = useMutation({ mutationFn: () => sendHubPost(network.id, hub.code, { body: draft.trim(), kind, ...(reply ? { reply_to_id: reply.id } : {}) }, files),
    onSuccess: () => { setDraft(''); setFiles([]); setReply(null); setKind('message'); void qc.invalidateQueries({ queryKey: key }); void qc.invalidateQueries({ queryKey: ['state-hubs'] }) } })
  const update = useMutation({ mutationFn: ({ id, ...data }: { id: string; pinned?: boolean; resolved?: boolean }) => updateHubMessage(network.id, hub.code, id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: key }) } })
  return <>
    <div className="nc-thread-heading"><div><h2><Hash size={21} />{hub.name}</h2><p>{hub.code} · Your state chat hub</p></div><button className="nc-text-button" onClick={() => setInfo(!info)} aria-expanded={info}><Info size={16} />Conversation info</button></div>
    <p className="nc-audience">A shared space for {hub.name} shops. Staff at each participating shop can read and reply.</p>
    {info && <div className="nc-info">Your shop’s network and state assignment controls membership. Direct messages remain available across states. Pins and stock-request status are shared with the hub.</div>}
    <div className="nc-inline-actions"><button className="nc-text-button" onClick={() => setPinnedOnly(!pinnedOnly)} aria-pressed={pinnedOnly}><Pin size={14} />{pinnedOnly ? 'Show all messages' : 'Pinned messages'}</button>{hub.unread > 0 && <span className="nc-state-tag">{hub.unread} unread</span>}</div>
    <ErrorNotice error={messages.error ?? read.error ?? send.error ?? update.error} />
    <div className="nc-message-list" aria-label={hub.name + ' messages'}>
      {messages.hasNextPage && <button className="nc-text-button" disabled={messages.isFetchingNextPage} onClick={() => void messages.fetchNextPage()}>Load earlier messages</button>}
      {messages.isPending && <p role="status">Loading messages…</p>}
      {!messages.isPending && !rows.length && <div className="nc-empty">Be the first to say hello to your state.</div>}
      {pinnedOnly && !rows.some(m => m.pinned) && <p className="nc-muted">No pinned messages in the loaded history. Load earlier messages to see older pins.</p>}
      {rows.filter(m => !pinnedOnly || m.pinned).map(m => <article className={'nc-message' + (m.mine ? ' mine' : '')} key={m.id}>
        <small>{m.sender_name} · {m.shop_name} · {when(m.created_at)}</small>
        <div className={'nc-bubble' + (m.kind === 'stock_request' ? ' stock' : '')}>
          {m.pinned && <span className="nc-eyebrow"><Pin size={12} /> Pinned</span>}
          {m.reply_preview && <blockquote>{m.reply_preview}</blockquote>}
          {m.kind === 'stock_request' && <strong className="nc-stock-label">{m.resolved_at ? 'Resolved stock request' : 'Open stock request'}</strong>}
          <p>{m.body}</p><MessageFiles attachments={m.attachments ?? []} />
          {m.kind === 'stock_request' && m.can_moderate && <button className="nc-text-button" disabled={update.isPending} onClick={() => update.mutate({ id: m.id, resolved: !m.resolved_at })}>{m.resolved_at ? 'Reopen request' : 'Mark resolved'}</button>}
        </div>
        {hub.can_post && <div className="nc-inline-actions"><button className="nc-text-button" onClick={() => setReply(m)}><Reply size={13} />Reply</button>{m.can_moderate && <button className="nc-text-button" disabled={update.isPending} onClick={() => update.mutate({ id: m.id, pinned: !m.pinned })}><Pin size={13} />{m.pinned ? 'Unpin' : 'Pin'}</button>}</div>}
      </article>)}<div ref={bottom} />
    </div>
    {hub.can_post ? <form className="nc-composer" onSubmit={e => { e.preventDefault(); if ((draft.trim() || files.length) && !send.isPending) send.mutate() }}>
      {reply && <div className="nc-reply-preview">Replying to {reply.sender_name}: {reply.body.slice(0, 100)}<button type="button" onClick={() => setReply(null)}>Cancel reply</button></div>}
      <label className="nc-sr-only" htmlFor="hub-message">Message {hub.name}</label><textarea id="hub-message" maxLength={2000} placeholder={'Message ' + hub.name + '…'} value={draft} onChange={e => setDraft(e.target.value)} disabled={send.isPending} />
      <FilePicker files={files} setFiles={setFiles} disabled={send.isPending} /><div className="nc-composer-actions"><label>Post type<select value={kind} onChange={e => setKind(e.target.value)} disabled={send.isPending}><option value="message">Message</option><option value="stock_request">Stock request</option></select></label><button className="nc-button primary" disabled={(!draft.trim() && !files.length) || send.isPending}><Send size={15} />{send.isPending ? 'Sending…' : 'Send message'}</button></div>
    </form> : <p className="nc-help">Your network role has read-only access to this hub.</p>}
  </>
}

function DirectThread({ networkId, conversation, conversationId, recipient, recipientName, onSent }: { networkId: string; conversation?: NetworkConversation; conversationId: string | null; recipient: string | null; recipientName?: string; onSent: (id: string) => void }) {
  const { tenantId } = useAuth()
  const qc = useQueryClient()
  const [draft, setDraft] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const key = ['network-thread', tenantId, conversationId]
  const messages = useQuery({ queryKey: key, queryFn: () => api.get<NetworkMessage[]>(`/network-messages/conversations/${conversationId}/messages`).then(r => r.data), enabled: !!conversationId, refetchInterval: 15_000 })
  useEffect(() => { if (messages.data) { void qc.invalidateQueries({ queryKey: ['network-conversations'] }); void qc.invalidateQueries({ queryKey: ['inbox-count'] }) } }, [messages.data, qc])
  const directBottom = useRef<HTMLDivElement>(null)
  const latestId = messages.data?.at(-1)?.id
  useEffect(() => { directBottom.current?.scrollIntoView?.({ block: 'nearest' }) }, [latestId])
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const send = useMutation({ mutationFn: () => sendDirectPost(networkId, recipient!, draft.trim(), files),
    onSuccess: data => {
      setDraft(''); setFiles([])
      void qc.invalidateQueries({ queryKey: ['network-conversations'] })
      if (conversationId) void qc.invalidateQueries({ queryKey: key })
      else if (active.current) onSent(data.conversation_id)
    } })
  return <>
    <div className="nc-thread-heading"><div><h2>{recipientName ?? 'Shop conversation'}</h2><p>Direct shop conversation</p></div></div>
    <p className="nc-audience">Shared shop inbox · Staff at both shops can read and reply.</p>
    <ErrorNotice error={messages.error ?? send.error} />
    <div className="nc-message-list">{messages.isPending && conversationId && <p role="status">Loading messages…</p>}
      {messages.data?.length === 200 && <p className="nc-muted">Showing the latest 200 messages.</p>}
      {(messages.data ?? []).map(m => <article key={m.id} className={'nc-message' + (m.mine ? ' mine' : '')}><small>{m.sender_name ?? (m.mine ? 'Your shop' : conversation?.other_name)} · {when(m.created_at)}</small><div className="nc-bubble"><p>{m.body}</p><MessageFiles attachments={m.attachments ?? []} /></div></article>)}
      {!conversationId && <p className="nc-muted">Start a new conversation with this shop.</p>}<div ref={directBottom} />
    </div>
    <form className="nc-composer" onSubmit={e => { e.preventDefault(); if (recipient && (draft.trim() || files.length) && !send.isPending) send.mutate() }}>
      <label className="nc-sr-only" htmlFor="direct-message">Direct message</label><textarea id="direct-message" value={draft} maxLength={2000} onChange={e => setDraft(e.target.value)} disabled={send.isPending} placeholder={'Message ' + (recipientName ?? 'this shop') + '…'} />
      <FilePicker files={files} setFiles={setFiles} disabled={send.isPending} /><div className="nc-composer-actions"><span className="nc-muted">{draft.length}/2000</span><button className="nc-button primary" disabled={!recipient || (!draft.trim() && !files.length) || send.isPending}><Send size={15} />{send.isPending ? 'Sending…' : 'Send message'}</button></div>
    </form>
  </>
}

function Announcements({ network, onHub }: { network: MessagingNetwork; onHub: (code: string) => void }) {
  const { tenantId } = useAuth()
  const qc = useQueryClient()
  const key = ['network-announcements', tenantId, network.id]
  const [filter, setFilter] = useState('all')
  const [compose, setCompose] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [draft, setDraft] = useState<AnnouncementDraft>({ title: '', body: '', state_code: network.can_publish_network ? null : network.publish_states[0] ?? null, category: 'update', pinned: false, requires_confirmation: false })
  const query = useInfiniteQuery({ queryKey: key, initialPageParam: 0,
    queryFn: ({ pageParam }) => listAnnouncements(network.id, pageParam),
    getNextPageParam: (page, pages) => page.has_more ? pages.reduce((sum, p) => sum + p.announcements.length, 0) : undefined,
    refetchInterval: 30_000 })
  const rows = query.data?.pages.flatMap(p => p.announcements) ?? []
  const acknowledge = useMutation({ mutationFn: ({ id, confirm }: { id: string; confirm: boolean }) => acknowledgeAnnouncement(network.id, id, confirm),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: key }) } })
  const publish = useMutation({ mutationFn: () => publishAnnouncement(network.id, draft),
    onSuccess: () => { setCompose(false); setDraft({ ...draft, title: '', body: '' }); void qc.invalidateQueries({ queryKey: key }) } })
  const visible = rows.filter(a => filter === 'all' || filter === 'unread' && !a.read || filter === 'network' && !a.state_code || filter === 'state' && a.state_code === network.own_state)
  return <section>
    <div className="nc-announcement-toolbar"><div className="nc-inline-actions">{[['all', 'All updates'], ['state', network.own_state ? stateNames[network.own_state] : 'My state'], ['network', 'Network-wide'], ['unread', 'Unread']].map(([value, label]) => <button key={value} className={'nc-filter' + (filter === value ? ' active' : '')} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
      {(network.can_publish_network || network.publish_states.length > 0) && <button className="nc-button primary" onClick={() => setCompose(!compose)} aria-expanded={compose}>New announcement</button>}
    </div>
    <ErrorNotice error={query.error ?? acknowledge.error ?? publish.error} />
    {compose && <form className="nc-publish" onSubmit={e => { e.preventDefault(); publish.mutate() }}><h2>Publish an announcement</h2>
      <label>Audience<select value={draft.state_code ?? ''} onChange={e => setDraft({ ...draft, state_code: e.target.value || null })}>{network.can_publish_network && <option value="">All shops in this network</option>}{network.publish_states.map(code => <option key={code} value={code}>{stateNames[code]}</option>)}</select></label>
      <label>Category<select value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value as AnnouncementDraft['category'] })}><option value="update">Update</option><option value="training">Training</option><option value="important">Important</option></select></label>
      <label>Title<input required maxLength={200} value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label>
      <label>Message<textarea required maxLength={10000} rows={5} value={draft.body} onChange={e => setDraft({ ...draft, body: e.target.value })} /></label>
      <label className="nc-check"><input type="checkbox" checked={draft.pinned} onChange={e => setDraft({ ...draft, pinned: e.target.checked })} />Pin this update</label><label className="nc-check"><input type="checkbox" checked={draft.requires_confirmation} onChange={e => setDraft({ ...draft, requires_confirmation: e.target.checked })} />Ask each shop to confirm receipt</label>
      <p className="nc-muted">This publishes to {draft.state_code ? stateNames[draft.state_code] : 'every shop in this network'}.</p>
      <button className="nc-button primary" disabled={publish.isPending || !draft.title.trim() || !draft.body.trim()}>{publish.isPending ? 'Publishing…' : 'Publish announcement'}</button>
    </form>}
    <div className="nc-announcement-layout"><div className="nc-announcement-feed">
      {query.isPending && <p role="status">Loading updates…</p>}
      {visible.map(a => <article key={a.id} className={'nc-announcement ' + a.category + (a.pinned ? ' pinned' : '')}>
        <div className="nc-inline-actions">{a.pinned && <span className="nc-state-tag"><Pin size={12} />PINNED</span>}<span className="nc-state-tag">{a.state_code ? stateNames[a.state_code] : 'All Minit shops'}</span><span className="nc-state-tag">{a.category}</span>{!a.read && <span className="nc-new">NEW</span>}</div>
        <h2>{a.title}</h2><p className="nc-muted">{a.author_name} · {when(a.created_at)}</p>
        <p className={'nc-announcement-body' + (expanded === a.id ? ' expanded' : '')}>{a.body}</p>
        <div className="nc-inline-actions"><button className="nc-text-button" onClick={() => { setExpanded(expanded === a.id ? null : a.id); if (!a.read) acknowledge.mutate({ id: a.id, confirm: false }) }}>{expanded === a.id ? 'Collapse' : 'Read update'}</button>
          {!a.read && <button className="nc-text-button" disabled={acknowledge.isPending} onClick={() => acknowledge.mutate({ id: a.id, confirm: false })}>Mark read</button>}
          {a.requires_confirmation && <button className="nc-button" disabled={a.confirmed || acknowledge.isPending} onClick={() => acknowledge.mutate({ id: a.id, confirm: true })}>{a.confirmed ? <><CheckCheck size={15} />Shop confirmed</> : <><Check size={15} />Confirm received</>}</button>}
          {a.state_code && <button className="nc-text-button" onClick={() => onHub(a.state_code!)}>Open state hub →</button>}
        </div>
      </article>)}
      {!query.isPending && !visible.length && <div className="nc-empty"><Megaphone /><h2>No updates here yet</h2><p>Network and state announcements will appear here.</p></div>}
      {query.hasNextPage && <button className="nc-button" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>Load older updates</button>}
    </div><aside className="nc-announcement-info"><span className="nc-eyebrow">YOUR UPDATES</span><h2>Network{network.own_state ? ' + ' + stateNames[network.own_state] : ''}</h2><p>You receive network announcements and updates for states available to your account.</p><span className="nc-state-tag">{rows.filter(a => !a.read).length} unread in loaded updates</span><h3>Posted by</h3><p>Support Office → All shops<br />State managers → Their state</p><h3>Keep the chat flowing</h3><p>Announcements stay easy to find. Questions continue in your state hub.</p>{network.own_state && <button className="nc-button" onClick={() => onHub(network.own_state!)}>Open my state hub</button>}</aside></div>
  </section>
}

