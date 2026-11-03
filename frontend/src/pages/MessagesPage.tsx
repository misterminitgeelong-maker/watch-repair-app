import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  getApiErrorMessage,
  getNetworkContacts,
  getNetworkConversations,
  getNetworkMessages,
  sendNetworkMessage,
} from '@/lib/api'
import { Button, Card, EmptyState, PageHeader, Select, Spinner, Textarea } from '@/components/ui'

function when(s: string) {
  return new Date(s).toLocaleString('en-AU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

/** Direct messages between sites of one network (shops, mobile operators, Support office). */
export default function MessagesPage() {
  const qc = useQueryClient()
  const [params, setParams] = useSearchParams()
  const selected = params.get('c')
  const [newTo, setNewTo] = useState('')
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const bottom = useRef<HTMLDivElement>(null)

  const { data: convs, isLoading } = useQuery({
    queryKey: ['network-conversations'],
    queryFn: () => getNetworkConversations().then(r => r.data),
    refetchInterval: 30_000,
  })
  const { data: contacts } = useQuery({
    queryKey: ['network-contacts'],
    queryFn: () => getNetworkContacts().then(r => r.data),
  })
  const current = (convs ?? []).find(c => c.id === selected) ?? null
  const { data: thread } = useQuery({
    queryKey: ['network-thread', selected],
    queryFn: () => getNetworkMessages(selected as string).then(r => r.data),
    enabled: !!selected,
    refetchInterval: 15_000,
  })

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
    if (selected) {
      void qc.invalidateQueries({ queryKey: ['network-conversations'] })
      void qc.invalidateQueries({ queryKey: ['inbox-count'] })
    }
  }, [thread, selected, qc])

  const send = useMutation({
    mutationFn: (tenantId: string) => sendNetworkMessage(tenantId, draft.trim()).then(r => r.data),
    onSuccess: async () => {
      setDraft('')
      setError('')
      const fresh = await qc.fetchQuery({
        queryKey: ['network-conversations'],
        queryFn: () => getNetworkConversations().then(r => r.data),
        staleTime: 0,
      })
      const target = fresh.find(c => c.other_tenant_id === (current?.other_tenant_id ?? newTo))
      if (target) setParams({ c: target.id })
      setNewTo('')
      void qc.invalidateQueries({ queryKey: ['network-thread'] })
    },
    onError: e => setError(getApiErrorMessage(e, 'Could not send the message.')),
  })

  const recipient = current?.other_tenant_id ?? newTo

  return (
    <div>
      <PageHeader title="Messages" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Message other shops, mobile operators and the Support office in your network. Only you and the other site can read a conversation.
      </p>
      <div className="grid gap-4 md:grid-cols-[18rem_1fr]">
        <Card className="overflow-hidden self-start">
          <div className="p-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
            <Select label="New message to" value={newTo} onChange={e => { setNewTo(e.target.value); setParams({}) }}>
              <option value="">Choose a site…</option>
              {(contacts ?? []).map(c => (
                <option key={c.tenant_id} value={c.tenant_id}>{c.name}</option>
              ))}
            </Select>
          </div>
          {isLoading ? (
            <Spinner />
          ) : (convs ?? []).length === 0 ? (
            <p className="p-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No conversations yet.</p>
          ) : (
            (convs ?? []).map(c => (
              <button
                key={c.id}
                type="button"
                onClick={() => { setNewTo(''); setParams({ c: c.id }) }}
                className="w-full text-left px-4 py-3 block"
                style={{
                  borderBottom: '1px solid var(--ms-border)',
                  background: c.id === selected ? 'var(--ms-surface-2, rgba(0,0,0,0.04))' : undefined,
                }}
              >
                <span className="flex justify-between gap-2 text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
                  <span className="truncate">{c.other_name}</span>
                  {c.unread > 0 && (
                    <span className="shrink-0 rounded-full px-2 text-xs text-white" style={{ background: 'var(--ms-accent)' }}>{c.unread}</span>
                  )}
                </span>
                <span className="block text-xs truncate" style={{ color: 'var(--ms-text-muted)' }}>{c.last_body}</span>
              </button>
            ))
          )}
        </Card>

        <Card className="p-4">
          {!recipient ? (
            <EmptyState message="Pick a conversation, or choose a site to start a new one." />
          ) : (
            <>
              <p className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>
                {current?.other_name ?? (contacts ?? []).find(c => c.tenant_id === newTo)?.name}
              </p>
              <div className="space-y-2 mb-4 max-h-[50vh] overflow-y-auto">
                {(thread ?? []).map(m => (
                  <div key={m.id} className={m.mine ? 'text-right' : ''}>
                    <div
                      className="inline-block rounded-lg px-3 py-2 text-sm text-left max-w-[85%] whitespace-pre-wrap"
                      style={{
                        background: m.mine ? 'var(--ms-accent)' : 'rgba(0,0,0,0.06)',
                        color: m.mine ? '#fff' : 'var(--ms-text)',
                      }}
                    >
                      {m.body}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                      {m.mine ? 'You' : (m.sender_name ?? current?.other_name)} · {when(m.created_at)}
                    </div>
                  </div>
                ))}
                <div ref={bottom} />
              </div>
              <Textarea
                label="Message"
                value={draft}
                maxLength={2000}
                onChange={e => setDraft(e.target.value)}
              />
              <div className="flex items-center gap-3 mt-3">
                <Button disabled={!draft.trim() || send.isPending} onClick={() => send.mutate(recipient)}>Send</Button>
                {error && <span role="alert" className="text-sm" style={{ color: 'var(--ms-error)' }}>{error}</span>}
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
