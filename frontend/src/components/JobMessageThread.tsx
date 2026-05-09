import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { getJobMessages, sendJobMessage, type JobThreadMessage } from '@/lib/api'
import { Spinner } from '@/components/ui'

function formatTime(s: string) {
  const d = new Date(s)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86400_000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString())
    return `Yesterday ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
  return (
    d.toLocaleDateString([], { day: 'numeric', month: 'short' }) +
    ' ' +
    d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  )
}

interface Props {
  jobId: string
}

export default function JobMessageThread({ jobId }: Props) {
  const qc = useQueryClient()
  const bottomRef = useRef<HTMLDivElement>(null)
  const [text, setText] = useState('')

  const { data: messages, isLoading } = useQuery({
    queryKey: ['job-messages', jobId],
    queryFn: () => getJobMessages(jobId).then(r => r.data),
    refetchInterval: 15_000,
  })

  const sendMut = useMutation({
    mutationFn: (body: string) => sendJobMessage(jobId, body),
    onSuccess: () => {
      setText('')
      void qc.invalidateQueries({ queryKey: ['job-messages', jobId] })
    },
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSend() {
    const trimmed = text.trim()
    if (!trimmed || sendMut.isPending) return
    sendMut.mutate(trimmed)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (isLoading) return <Spinner />

  return (
    <div
      className="flex flex-col rounded-2xl overflow-hidden"
      style={{
        height: 'calc(100vh - 280px)',
        minHeight: 360,
        backgroundColor: '#f0f0f0',
      }}
    >
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {(!messages || messages.length === 0) && (
          <p className="text-sm text-center mt-8" style={{ color: '#999' }}>
            No messages yet
          </p>
        )}

        {messages?.map((msg: JobThreadMessage) => {
          /* ── System / automated SMS ── */
          if (msg.direction === 'system') {
            return (
              <div key={msg.id} className="flex justify-center py-2">
                <div className="text-center max-w-xs">
                  <span
                    className="inline-block text-xs px-3 py-1 rounded-full"
                    style={{ backgroundColor: '#d0d0d0', color: '#555' }}
                  >
                    {msg.event?.replace(/_/g, ' ')}
                    {msg.status === 'dry_run' && ' · dry run'}
                  </span>
                  <p className="text-xs mt-0.5" style={{ color: '#aaa' }}>
                    {msg.body.length > 60 ? msg.body.slice(0, 60) + '…' : msg.body}
                  </p>
                  <p className="text-xs" style={{ color: '#bbb' }}>{formatTime(msg.created_at)}</p>
                </div>
              </div>
            )
          }

          /* ── Outbound (shop → customer) ── */
          if (msg.direction === 'outbound') {
            return (
              <div key={msg.id} className="flex flex-col items-end">
                <div
                  className="max-w-[75%] px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap"
                  style={{
                    backgroundColor: '#1E88E5',
                    color: '#fff',
                    borderRadius: '18px 18px 4px 18px',
                    wordBreak: 'break-word',
                  }}
                >
                  {msg.body}
                </div>
                <p className="text-xs mt-0.5 mr-1" style={{ color: '#999' }}>
                  {formatTime(msg.created_at)}
                </p>
              </div>
            )
          }

          /* ── Inbound (customer → shop) ── */
          return (
            <div key={msg.id} className="flex flex-col items-start">
              <div
                className="max-w-[75%] px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap"
                style={{
                  backgroundColor: '#fff',
                  color: '#111',
                  borderRadius: '18px 18px 18px 4px',
                  wordBreak: 'break-word',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
                }}
              >
                {msg.body}
              </div>
              <p className="text-xs mt-0.5 ml-1" style={{ color: '#999' }}>
                {msg.from_phone ?? 'Customer'} · {formatTime(msg.created_at)}
              </p>
            </div>
          )
        })}

        <div ref={bottomRef} />
      </div>

      {/* Error */}
      {sendMut.isError && (
        <p className="text-xs text-center py-1" style={{ color: '#E53935', backgroundColor: '#fff' }}>
          Failed to send — please try again
        </p>
      )}

      {/* Compose bar */}
      <div
        className="flex items-end gap-2 px-3 py-2"
        style={{ backgroundColor: '#f0f0f0', borderTop: '1px solid #ddd' }}
      >
        <div
          className="flex-1 flex items-end rounded-3xl px-4 py-2"
          style={{ backgroundColor: '#fff', border: '1px solid #ddd', minHeight: 44 }}
        >
          <textarea
            className="flex-1 resize-none bg-transparent text-sm outline-none"
            style={{ color: '#111', minHeight: 24, maxHeight: 100, lineHeight: '1.4' }}
            placeholder="Text message"
            rows={1}
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sendMut.isPending}
          />
        </div>
        <button
          onClick={handleSend}
          disabled={!text.trim() || sendMut.isPending}
          className="shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all"
          style={{
            backgroundColor: text.trim() && !sendMut.isPending ? '#1E88E5' : '#ccc',
            color: '#fff',
          }}
          aria-label="Send"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
