import React from 'react'
import { Link } from 'react-router-dom'

import { initialsOf, techColor } from './techAvatar'

export interface JobCardProps {
  jobNumber: string
  title: string
  description?: string | null
  customerName?: string | null
  priority?: string | null
  daysInShop: number
  quoteCents?: number
  techName?: string | null
  techKey?: string | null
  accentColor: string
  href: string
  selected?: boolean
  extras?: React.ReactNode
  onDragStart?: (e: React.DragEvent<HTMLDivElement>) => void
  onDragEnd?: (e: React.DragEvent<HTMLDivElement>) => void
  draggable?: boolean
}

function PriorityPill({ priority }: { priority?: string | null }) {
  if (!priority) return null
  const p = priority.toLowerCase()
  if (p !== 'urgent' && p !== 'high') return null
  const bg = p === 'urgent' ? '#FEEEED' : '#FFF0E0'
  const text = p === 'urgent' ? '#8B3A2A' : '#8A5010'
  const label = p === 'urgent' ? 'Urgent' : 'High'
  return (
    <span
      style={{
        backgroundColor: bg,
        color: text,
        fontSize: 10,
        fontWeight: 700,
        padding: '2px 7px',
        borderRadius: 99,
        letterSpacing: '0.03em',
      }}
    >
      {label}
    </span>
  )
}

function AgingPill({ days }: { days: number }) {
  let bg = '#EBF8EF'
  let text = '#3A6A3A'
  if (days >= 14) {
    bg = '#FEEEED'
    text = '#8B3A2A'
  } else if (days >= 7) {
    bg = '#FFF0E0'
    text = '#9A5010'
  }
  return (
    <span
      style={{
        backgroundColor: bg,
        color: text,
        fontSize: 10,
        fontWeight: 700,
        padding: '2px 7px',
        borderRadius: 99,
      }}
    >
      {days}d
    </span>
  )
}

export default function JobCard({
  jobNumber,
  title,
  description,
  customerName,
  priority,
  daysInShop,
  quoteCents,
  techName,
  techKey,
  accentColor,
  href,
  selected,
  extras,
  onDragStart,
  onDragEnd,
  draggable,
}: JobCardProps) {
  const tech = techColor(techKey ?? techName ?? null)

  return (
    <Link
      to={href}
      draggable={draggable}
      onDragStart={onDragStart as unknown as React.DragEventHandler<HTMLAnchorElement>}
      onDragEnd={onDragEnd as unknown as React.DragEventHandler<HTMLAnchorElement>}
      className="block"
      style={{
        backgroundColor: 'var(--ms-surface)',
        border: '1px solid var(--ms-border)',
        borderLeft: `3px solid ${accentColor}`,
        borderRadius: 'var(--ms-radius-sm)',
        padding: '11px 12px',
        marginBottom: 8,
        boxShadow: selected ? `0 0 0 2px ${accentColor}22, var(--ms-shadow)` : 'var(--ms-shadow)',
        borderColor: selected ? accentColor : 'var(--ms-border)',
        cursor: draggable ? 'grab' : 'pointer',
        textDecoration: 'none',
        color: 'inherit',
        display: 'block',
      }}
    >
      <div className="flex items-start justify-between gap-2">
        <div style={{ fontSize: 10, fontWeight: 700, color: accentColor, letterSpacing: '0.03em' }}>
          #{jobNumber}
        </div>
        <div className="flex items-center gap-1.5">
          <PriorityPill priority={priority} />
          <AgingPill days={daysInShop} />
        </div>
      </div>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ms-text)', marginTop: 4, lineHeight: 1.3 }}>
        {title}
      </div>
      {description && (
        <div
          style={{
            fontSize: 11,
            color: 'var(--ms-text-muted)',
            marginTop: 2,
            lineHeight: 1.35,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}
        >
          {description}
        </div>
      )}
      {customerName && (
        <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--ms-text-mid)', marginTop: 5 }}>
          {customerName}
        </div>
      )}
      {extras && <div style={{ marginTop: 6 }}>{extras}</div>}
      {(techName || quoteCents !== undefined) && (
        <div
          className="flex items-center justify-between"
          style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--ms-border)' }}
        >
          <div className="flex items-center gap-2" style={{ minHeight: 20 }}>
            {techName ? (
              <>
                <span
                  aria-hidden
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    backgroundColor: tech.bg,
                    color: tech.text,
                    fontSize: 9,
                    fontWeight: 700,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    letterSpacing: '0.02em',
                  }}
                >
                  {initialsOf(techName)}
                </span>
                <span style={{ fontSize: 10, color: 'var(--ms-text-muted)' }}>{techName}</span>
              </>
            ) : (
              <span style={{ fontSize: 10, color: 'var(--ms-text-muted)' }}>Unassigned</span>
            )}
          </div>
          {quoteCents !== undefined && (
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ms-text)' }}>
              ${(quoteCents / 100).toFixed(2)}
            </div>
          )}
        </div>
      )}
    </Link>
  )
}
