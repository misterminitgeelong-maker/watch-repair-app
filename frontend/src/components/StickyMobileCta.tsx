import { Link } from 'react-router-dom'

const CSS = `
.ms-sticky-cta{display:none}
@media (max-width:640px){
  .ms-sticky-cta{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:40;gap:8px;padding:10px 16px calc(10px + env(safe-area-inset-bottom));background:#1B2B3E;border-top:1px solid #C9A24B}
  .ms-sticky-cta a{flex:1;display:flex;align-items:center;justify-content:center;min-height:44px;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;text-decoration:none;border-radius:4px}
  .ms-sticky-cta a.primary{background:#C8402A;color:#fff}
  .ms-sticky-cta a.secondary{border:1px solid #F7F5F0;color:#F7F5F0}
  body{padding-bottom:64px}
}`

/** Fixed bottom bar on phones for the public marketing pages. */
export default function StickyMobileCta() {
  return (
    <>
      <style>{CSS}</style>
      <nav className="ms-sticky-cta" aria-label="Get started">
        <Link to="/signup" className="primary">Start free trial</Link>
        <Link to="/login?demo=1" className="secondary">Try the demo</Link>
      </nav>
    </>
  )
}
