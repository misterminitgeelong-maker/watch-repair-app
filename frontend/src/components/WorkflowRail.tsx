import React from 'react'
import { Check } from 'lucide-react'

export interface WorkflowStep {
  key: string
  label: string
  statuses: readonly string[]
}

export const WATCH_WORKFLOW_STEPS: readonly WorkflowStep[] = [
  { key: 'received', label: 'Received', statuses: ['awaiting_quote', 'awaiting_customer_details'] },
  { key: 'quoted', label: 'Quoted', statuses: ['awaiting_go_ahead', 'quote_sent'] },
  {
    key: 'approved',
    label: 'Approved',
    statuses: ['go_ahead', 'awaiting_parts', 'parts_to_order', 'sent_to_labanda', 'quoted_by_labanda'],
  },
  { key: 'working', label: 'In Workshop', statuses: ['working_on', 'service'] },
  { key: 'complete', label: 'Completed', statuses: ['completed'] },
  { key: 'collected', label: 'Collected', statuses: ['awaiting_collection', 'collected'] },
] as const

export const SHOE_WORKFLOW_STEPS: readonly WorkflowStep[] = [
  { key: 'received', label: 'Received', statuses: ['awaiting_quote', 'awaiting_customer_details'] },
  { key: 'quoted', label: 'Quoted', statuses: ['awaiting_go_ahead', 'quote_sent'] },
  { key: 'working', label: 'In Work', statuses: ['go_ahead', 'awaiting_parts', 'working_on', 'service'] },
  { key: 'complete', label: 'Completed', statuses: ['completed'] },
  { key: 'collected', label: 'Collected', statuses: ['awaiting_collection', 'collected'] },
] as const

interface WorkflowRailProps {
  steps: readonly WorkflowStep[]
  currentStatus: string
  onStepClick?: (stepStatus: string) => void
  disabled?: boolean
}

export function WorkflowRail({ steps, currentStatus, onStepClick, disabled }: WorkflowRailProps) {
  const currentIdx = steps.findIndex(s => s.statuses.includes(currentStatus))
  const activeIdx = currentIdx < 0 ? 0 : currentIdx

  return (
    <div
      style={{
        background: 'var(--ms-surface)',
        borderBottom: '1px solid var(--ms-border)',
        padding: '16px 24px',
      }}
    >
      <div className="flex items-start">
        {steps.map((step, idx) => {
          const state: 'past' | 'current' | 'future' =
            idx < activeIdx ? 'past' : idx === activeIdx ? 'current' : 'future'
          const clickable = !!onStepClick && !disabled
          const isLast = idx === steps.length - 1

          const nodeStyle: React.CSSProperties = {
            width: 30,
            height: 30,
            borderRadius: '50%',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'all 150ms ease',
            background:
              state === 'future' ? 'var(--ms-border)' : 'var(--ms-accent)',
            boxShadow: state === 'current' ? '0 0 0 4px var(--ms-accent-pop)' : 'none',
            cursor: clickable ? 'pointer' : 'default',
            border: 'none',
          }

          const labelStyle: React.CSSProperties = {
            fontSize: 10,
            letterSpacing: '0.01em',
            marginTop: 6,
            textAlign: 'center',
            fontWeight: state === 'current' ? 700 : 500,
            color:
              state === 'current'
                ? 'var(--ms-accent)'
                : state === 'past'
                ? 'var(--ms-text-mid)'
                : 'var(--ms-text-muted)',
          }

          return (
            <React.Fragment key={step.key}>
              <div className="flex flex-col items-center" style={{ minWidth: 64 }}>
                <button
                  type="button"
                  aria-label={`Set status to ${step.label}`}
                  aria-current={state === 'current' ? 'step' : undefined}
                  disabled={!clickable}
                  onClick={() => onStepClick?.(step.statuses[0])}
                  style={nodeStyle}
                >
                  {state === 'past' && <Check size={14} color="#fff" strokeWidth={3} />}
                  {state === 'current' && (
                    <span
                      aria-hidden
                      style={{ width: 8, height: 8, borderRadius: '50%', background: '#fff' }}
                    />
                  )}
                  {state === 'future' && (
                    <span
                      aria-hidden
                      style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--ms-text-muted)' }}
                    />
                  )}
                </button>
                <span style={labelStyle}>{step.label}</span>
              </div>
              {!isLast && (
                <div
                  aria-hidden
                  style={{
                    flex: 1,
                    height: 2,
                    margin: '14px 6px 0',
                    background: idx < activeIdx ? 'var(--ms-accent)' : 'var(--ms-border)',
                    transition: 'background 150ms ease',
                  }}
                />
              )}
            </React.Fragment>
          )
        })}
      </div>
    </div>
  )
}

export default WorkflowRail
