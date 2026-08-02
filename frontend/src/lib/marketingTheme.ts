/**
 * Shared marketing design tokens for Mainspring's public-facing pages
 * (landing, login, signup — anything outside the authenticated app shell).
 *
 * Deliberately editorial — stark rules, oatmeal + vermilion, zero border-radius,
 * zero shadows — to read as the opposite of the AI-heavy, blue/white repair-SaaS
 * category. This palette is marketing-only: it must never leak into the in-app
 * "Refined Warmth" (--ms-*) token set, and the app's tokens must never leak here.
 * Scope every use under the .mkt-landing class (or a shared ancestor of it).
 */

export const MKT = {
  paper: '#F7F7F4',
  oatmeal: '#EBE6DC',
  oatmealDeep: '#E2DACA',
  oatmealPanel: '#F1EEE7',
  ink: '#0A0A0A',
  vermilion: '#E8452A',
  vermilionDeep: '#B32D16',
  textBody: '#4A4A46',
  textMuted: '#6E6E68',
  ruleMid: '#D8D6CE',
  ruleLight: '#E4E2DA',
  greyChip: '#C4C2BA',
  statusGrey: '#6B7280',
  white: '#FFFFFF',
} as const

export const DOTS: Record<string, string> = {
  wait: MKT.vermilion,
  progress: MKT.ink,
  done: MKT.statusGrey,
  neutral: MKT.greyChip,
}

export const MARKETING_CSS = `
.mkt-landing {
  --mkt-paper: ${MKT.paper};
  --mkt-oatmeal: ${MKT.oatmeal};
  --mkt-oatmeal-deep: ${MKT.oatmealDeep};
  --mkt-oatmeal-panel: ${MKT.oatmealPanel};
  --mkt-oatmeal-hover: #E1DACB;
  --mkt-ink: ${MKT.ink};
  --mkt-ink-hover: #2E2E2B;
  --mkt-ink-row-hover: #EFEEE7;
  --mkt-vermilion: ${MKT.vermilion};
  --mkt-vermilion-hover: #FF5636;
  --mkt-vermilion-deep: ${MKT.vermilionDeep};
  font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
  background: var(--mkt-paper);
  color: var(--mkt-ink);
}
.mkt-landing * { box-sizing: border-box; }
.mkt-serif { font-family: Georgia, 'Palatino Linotype', Palatino, serif; }

@keyframes mktPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.mkt-pulse-dot { animation: mktPulse 1.6s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .mkt-pulse-dot { animation: none; }
}

@keyframes mktSlideUp { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
.mkt-slide-up { animation: mktSlideUp 0.6s cubic-bezier(.22,.68,0,1) both; }
.mkt-slide-up-delay { animation: mktSlideUp 0.7s cubic-bezier(.22,.68,0,1) 0.12s both; }
@media (prefers-reduced-motion: reduce) {
  .mkt-slide-up, .mkt-slide-up-delay { animation: none; }
}

.mkt-reveal {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.7s cubic-bezier(.22,.68,0,1), transform 0.7s cubic-bezier(.22,.68,0,1);
}
.mkt-reveal.mkt-shown { opacity: 1; transform: translateY(0); }
@media (prefers-reduced-motion: reduce) {
  .mkt-reveal { opacity: 1 !important; transform: none !important; transition: none !important; }
}

.mkt-landing a { text-decoration: none; }

.mkt-nav-cta { background: var(--mkt-ink); color: var(--mkt-paper); transition: background 160ms ease; }
.mkt-nav-cta:hover { background: var(--mkt-vermilion); }

.mkt-btn-primary { background: var(--mkt-vermilion); color: var(--mkt-ink); transition: background 160ms ease; }
.mkt-btn-primary:hover:not(:disabled) { background: var(--mkt-vermilion-hover); }
.mkt-btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.mkt-btn-outline-ink { background: transparent; color: var(--mkt-ink); border: 1px solid var(--mkt-ink); transition: background 160ms ease; }
.mkt-btn-outline-ink:hover:not(:disabled) { background: var(--mkt-oatmeal-hover); }
.mkt-btn-outline-ink:disabled { opacity: 0.6; cursor: not-allowed; }

.mkt-btn-close-primary { background: var(--mkt-ink); color: var(--mkt-white); transition: background 160ms ease; }
.mkt-btn-close-primary:hover { background: var(--mkt-ink-hover); }

.mkt-btn-close-outline { background: transparent; color: var(--mkt-ink); border: 1px solid var(--mkt-ink); transition: background 160ms ease; }
.mkt-btn-close-outline:hover { background: rgba(10,10,10,0.08); }

.mkt-row-hover { transition: background 120ms ease; }
.mkt-row-hover:hover { background: var(--mkt-ink-row-hover); }

.mkt-pricing-cta { background: var(--mkt-vermilion); color: var(--mkt-ink); transition: background 160ms ease; }
.mkt-pricing-cta:hover { background: var(--mkt-vermilion-hover); }

.mkt-input {
  background: var(--mkt-paper);
  border: 1px solid var(--mkt-ink);
  color: var(--mkt-ink);
  transition: background 120ms ease;
}
.mkt-input::placeholder { color: #9A9890; }
.mkt-input:focus { outline: none; background: #FFFFFF; }
.mkt-input:focus-visible { outline: 2px solid var(--mkt-vermilion); outline-offset: 1px; }

.mkt-tab:focus-visible,
.mkt-btn-primary:focus-visible,
.mkt-btn-outline-ink:focus-visible,
.mkt-nav-cta:focus-visible,
.mkt-pricing-cta:focus-visible,
.mkt-btn-close-primary:focus-visible,
.mkt-btn-close-outline:focus-visible {
  outline: 2px solid var(--mkt-vermilion);
  outline-offset: 2px;
}
`
