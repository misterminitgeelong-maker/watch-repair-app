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
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (d.toDateString() === yesterday.toDateString()) return `Yesterday ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function eventLabel(event: string) {
  return event.replace(/_/g, ' ')
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

  // Scroll to bottom whenever messages load or a new one arrives
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
    <div className="flex flex-col" style={{ height: 'calc(100vh - 280px)', minHeight: 320 }}>
      {/* Message list */}
      <div className="flex-1 overflow-y-auto space-y-2 pb-2 pr-1">
        {(!messages || messages.length === 0) && (
          <p className="text-sm text-center py-8" style={{ color: 'var(--ms-text-muted)' }}>
            No messages yet. Send one below.
          </p>
        )}
        {messages?.map((msg: JobThreadMessage) => {
          if (msg.direction === 'system') {
            return (
              <div key={msg.id} className="flex justify-center">
                <div className="max-w-xs text-center">
                  <span
                    className="inline-block text-xs px-3 py-1.5 rounded-full"
                    style={{ backgroundColor: 'var(--ms-surface-raised, #f3f3f3)', color: 'var(--ms-text-muted)', border: '1px solid var(--ms-border)' }}
                  >
                    {msg.body.length > 80 ? msg.body.slice(0, 80) + '…' : msg.body}
                  </span>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                    Auto · {eventLabel(msg.event ?? '')} · {formatTime(msg.created_at)}
                    {msg.status === 'dry_run' && ' · dry run'}
                  </p>
                </div>
              </div>
            )
          }

          const isOutbound = msg.direction === 'outbound'
          return (
            <div key={msg.id} className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}>
              <div className="max-w-[75%]">
                <div
                  className="px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
                  style={
                    isOutbound
                      ? { backgroundColor: 'var(--ms-accent)', color: '#fff', borderBottomRightRadius: 4 }
                      : { backgroundColor: 'var(--ms-surface-raised, #ececec)', color: 'var(--ms-text)', border: '1px solid var(--ms-border)', borderBottomLeftRadius: 4 }
                  }
                >
                  {msg.body}
                </div>
                <p className={`text-xs mt-0.5 ${isOutbound ? 'text-right' : 'text-left'}`} style={{ color: 'var(--ms-text-muted)' }}>
                  {isOutbound ? 'You' : (msg.from_phone ?? 'Customer')} · {formatTime(msg.created_at)}
                </p>
              </div>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>

      {/* Compose area */}
      <div
        className="mt-3 flex gap-2 items-end rounded-xl p-2"
        style={{ border: '1px solid var(--ms-border-strong)', backgroundColor: 'var(--ms-surface)' }}
      >
        <textarea
          className="flex-1 resize-none bg-transparent text-sm outline-none py-1.5 px-1"
          style={{ color: 'var(--ms-text)', minHeight: 40, maxHeight: 120 }}
          placeholder="Type a message… (Enter to send)"
          rows={1}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sendMut.isPending}
        />
        <button
          onClick={handleSend}
          disabled={!text.trim() || sendMut.isPending}
          className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center transition-opacity"
          style={{
            backgroundColor: 'var(--ms-accent)',
            color: '#fff',
            opacity: !text.trim() || sendMut.isPending ? 0.4 : 1,
          }}
          aria-label="Send"
        >
          <Send size={16} />
        </button>
      </div>

      {sendMut.isError && (
        <p className="text-xs mt-1 text-center" style={{ color: '#C96A5A' }}>Failed to send. Please try again.</p>
      )}
    </div>
  )
}
