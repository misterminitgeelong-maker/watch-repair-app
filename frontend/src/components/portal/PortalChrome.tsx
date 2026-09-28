import { useId, useMemo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Check } from 'lucide-react'
import { portalStageIndex, STAGE_ORDER, type PortalStage } from '@/lib/portalStatus'
import { MINIT_LOGO_SRC, minitBranchName, portalAccentStyle, STAGE_COPY } from './portalUtils'
import './portal.css'
import { clsx } from 'clsx'

/** Root wrapper — scopes the portal's look (tokens, fonts, motion). */
export function PortalPage({
  children,
  accent,
  minit = false,
}: {
  children: ReactNode
  accent?: string | null
  /** Mister Minit shop: Minit navy and red. */
  minit?: boolean
}) {
  return (
    <div className={clsx('pt', minit && 'pt--minit')} style={portalAccentStyle(accent)}>
      {children}
    </div>
  )
}

/**
 * A watch dial whose hands show the real time and keep moving: the seconds
 * hand sweeps like a mechanical movement. Pure CSS rotation — each hand starts
 * rotated to the current time, and the animation carries it on from there.
 * `spinner` runs the hands fast, as a loading indicator.
 */
export function PortalDial({ size = 132, spinner = false }: { size?: number; spinner?: boolean }) {
  const uid = `ptd${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  // Angles for the current time. Each hand is rotated to it statically (so it
  // reads right even with motion turned off), then spins from there.
  const angles = useMemo(() => {
    const now = new Date()
    const s = now.getSeconds() + now.getMilliseconds() / 1000
    const m = now.getMinutes() + s / 60
    const h = (now.getHours() % 12) + m / 60
    return { h: h * 30, m: m * 6, s: s * 6 }
  }, [])

  const ticks = Array.from({ length: 60 }, (_, i) => {
    const major = i % 5 === 0
    const a = (i * Math.PI) / 30
    const r1 = major ? 44 : 47
    const r2 = 50.5
    return (
      <line
        key={i}
        x1={60 + r1 * Math.sin(a)}
        y1={60 - r1 * Math.cos(a)}
        x2={60 + r2 * Math.sin(a)}
        y2={60 - r2 * Math.cos(a)}
        stroke={major ? '#D9BD8C' : 'rgba(244,241,234,0.35)'}
        strokeWidth={major ? 1.8 : 0.7}
        strokeLinecap="round"
      />
    )
  })

  const set = (deg: number) => (spinner ? undefined : `rotate(${deg.toFixed(2)} 60 60)`)

  return (
    <svg
      className={clsx('pt-dial', spinner && 'pt-dial--spinner')}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id={`${uid}-face`} cx="50%" cy="38%" r="70%">
          <stop offset="0%" stopColor="#2A2E37" />
          <stop offset="100%" stopColor="#0E1014" />
        </radialGradient>
        <linearGradient id={`${uid}-bezel`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#E6CFA2" />
          <stop offset="45%" stopColor="#8C6A36" />
          <stop offset="100%" stopColor="#D9BD8C" />
        </linearGradient>
      </defs>
      <circle cx="60" cy="60" r="58" fill={`url(#${uid}-bezel)`} />
      <circle cx="60" cy="60" r="55" fill={`url(#${uid}-face)`} />
      <circle cx="60" cy="60" r="38" fill="none" stroke="rgba(244,241,234,0.06)" strokeWidth="0.6" />
      <circle cx="60" cy="60" r="30" fill="none" stroke="rgba(244,241,234,0.05)" strokeWidth="0.6" />
      {ticks}
      <g transform={set(angles.h)}>
        <g className="pt-dial-hand pt-dial-hand--h">
          <path d="M58.4 62 L59.2 32 Q60 29 60.8 32 L61.6 62 Z" fill="#F4F1EA" />
        </g>
      </g>
      <g transform={set(angles.m)}>
        <g className="pt-dial-hand pt-dial-hand--m">
          <path d="M58.9 63 L59.5 17 Q60 14.5 60.5 17 L61.1 63 Z" fill="#F4F1EA" />
        </g>
      </g>
      <g transform={set(angles.s)}>
        <g className="pt-dial-hand pt-dial-hand--s">
          <line x1="60" y1="70" x2="60" y2="12" stroke="var(--pt-accent)" strokeWidth="1" strokeLinecap="round" />
          <circle cx="60" cy="70" r="2.2" fill="var(--pt-accent)" />
        </g>
      </g>
      <circle cx="60" cy="60" r="3.2" fill="#D9BD8C" />
      <circle cx="60" cy="60" r="1.3" fill="#0E1014" />
    </svg>
  )
}

/** The Mister Minit logo on its white plate. */
export function MinitLogoPlate({ small = false }: { small?: boolean }) {
  return (
    <span className={clsx('pt-logo-plate', small && 'pt-logo-plate--sm')}>
      <img src={MINIT_LOGO_SRC} alt="Mister Minit" />
    </span>
  )
}

/** The ink header every portal page opens with. */
export function PortalHero({
  eyebrow,
  title,
  lede,
  brand,
  barRight,
  showDial = true,
  children,
}: {
  eyebrow?: ReactNode
  title: ReactNode
  lede?: ReactNode
  brand?: { name?: string | null; logoUrl?: string | null; to?: string; minit?: boolean }
  barRight?: ReactNode
  showDial?: boolean
  children?: ReactNode
}) {
  const brandName = brand?.name?.trim() || (brand?.minit ? 'Mister Minit' : 'Mainspring')
  const mark = brand?.minit ? (
    <MinitLogoPlate />
  ) : brand?.logoUrl ? (
    <img src={brand.logoUrl} alt="" className="pt-wordmark-mark" />
  ) : (
    <span className="pt-wordmark-mark pt-serif" style={{ fontSize: 17 }}>
      {brandName.charAt(0).toUpperCase()}
    </span>
  )
  // Next to the Minit logo, "Mister Minit Chadstone" only needs "Chadstone".
  const shownName = brand?.minit ? minitBranchName(brandName) : brandName
  const wordmark = (
    <>
      {mark}
      {shownName && <span className="pt-wordmark-name">{shownName}</span>}
    </>
  )

  return (
    <header className="pt-hero">
      <div className="pt-hero-inner">
        <div className="pt-hero-bar">
          {brand?.to ? (
            <Link to={brand.to} className="pt-wordmark">{wordmark}</Link>
          ) : (
            <span className="pt-wordmark">{wordmark}</span>
          )}
          {barRight}
        </div>
        <div className="pt-hero-grid">
          <div className="pt-rise">
            {eyebrow && <p className="pt-eyebrow">{eyebrow}</p>}
            <h1 className="pt-display">{title}</h1>
            {lede && <p className="pt-lede">{lede}</p>}
          </div>
          {showDial && !brand?.minit && (
            <div className="pt-hero-dial pt-pop" style={{ animationDelay: '0.15s' }}>
              <PortalDial />
            </div>
          )}
        </div>
        {children}
      </div>
    </header>
  )
}

export function PortalBody({ children }: { children: ReactNode }) {
  return <main className="pt-body pt-stack">{children}</main>
}

/** Full-screen "working on it" state — the dial with its hands racing. */
export function PortalLoading({ label }: { label: string }) {
  return (
    <PortalPage>
      <div
        className="pt-hero"
        style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24 }}
        role="status"
      >
        <div style={{ textAlign: 'center' }} className="pt-rise">
          <div style={{ display: 'inline-block' }}>
            <PortalDial size={96} spinner />
          </div>
          <p className="pt-eyebrow" style={{ marginTop: 20 }}>{label}</p>
        </div>
      </div>
    </PortalPage>
  )
}

const STEP_SHORT: Record<PortalStage, string> = {
  received: 'Received',
  in_progress: 'Workshop',
  ready: 'Ready',
  collected: 'Collected',
}

export function StageStepper({ stage, live = true }: { stage: PortalStage; live?: boolean }) {
  const active = portalStageIndex(stage)
  return (
    <ol className="pt-steps" aria-label={`Progress: ${STAGE_COPY[stage]}`}>
      <span className="pt-steps-fill" style={{ width: `${active * 25}%` }} aria-hidden="true" />
      {STAGE_ORDER.map((s, idx) => {
        const done = idx < active || (idx === active && s === 'collected')
        const current = idx === active && !done
        return (
          <li
            key={s}
            className={[
              'pt-step',
              done && 'pt-step--done',
              current && 'pt-step--current',
              current && live && s !== 'collected' && 'pt-step--live',
            ].filter(Boolean).join(' ')}
            aria-current={current ? 'step' : undefined}
          >
            <span className="pt-step-dot">{done && <Check size={9} strokeWidth={4} />}</span>
            {STEP_SHORT[s]}
          </li>
        )
      })}
    </ol>
  )
}

/**
 * A bezel-style ring: 60 minute ticks around the icon, with the arc filled to
 * the job's stage.
 */
export function StageRing({
  stage,
  size = 64,
  children,
}: {
  stage: PortalStage
  size?: number
  children?: ReactNode
}) {
  const idx = portalStageIndex(stage)
  const fraction = stage === 'collected' ? 1 : (idx + 1) / STAGE_ORDER.length
  const r = 26
  const circ = 2 * Math.PI * r
  const ready = stage === 'ready'
  const stroke = ready ? 'var(--pt-brass)' : stage === 'collected' ? 'var(--pt-ok)' : 'var(--pt-accent)'

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" style={{ transform: 'rotate(-90deg)' }}>
        {Array.from({ length: 60 }, (_, i) => {
          const a = (i * Math.PI) / 30
          const major = i % 5 === 0
          return (
            <line
              key={i}
              x1={32 + 30.5 * Math.cos(a)}
              y1={32 + 30.5 * Math.sin(a)}
              x2={32 + (major ? 28.5 : 29.5) * Math.cos(a)}
              y2={32 + (major ? 28.5 : 29.5) * Math.sin(a)}
              stroke="var(--pt-line-strong)"
              strokeWidth={major ? 1 : 0.5}
            />
          )
        })}
        <circle cx="32" cy="32" r={r} fill="none" stroke="var(--pt-line)" strokeWidth="3" />
        <circle
          cx="32"
          cy="32"
          r={r}
          fill="none"
          stroke={stroke}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - fraction)}
          style={{ transition: 'stroke-dashoffset 1s cubic-bezier(0.2,0.8,0.2,1)' }}
        />
      </svg>
      <div
        style={{
          position: 'absolute',
          inset: size * 0.19,
          borderRadius: 999,
          display: 'grid',
          placeItems: 'center',
          background: ready
            ? 'color-mix(in srgb, var(--pt-brass) 16%, transparent)'
            : 'var(--pt-card-alt)',
          color: ready ? 'var(--pt-brass)' : 'var(--pt-text-mid)',
        }}
      >
        {children}
      </div>
    </div>
  )
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className="pt-switch"
      onClick={() => onChange(!checked)}
    />
  )
}

/** Segmented control with a sliding thumb. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: Array<{ value: T; label: string; icon?: ReactNode }>
  onChange: (v: T) => void
  label: string
}) {
  const idx = Math.max(0, options.findIndex((o) => o.value === value))
  return (
    <div className="pt-seg" role="group" aria-label={label}>
      <span
        className="pt-seg-thumb"
        aria-hidden="true"
        style={{
          width: `calc((100% - 8px) / ${options.length})`,
          transform: `translateX(${idx * 100}%)`,
        }}
      />
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  )
}
