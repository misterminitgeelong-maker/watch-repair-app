import { useEffect } from 'react'
import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  useEffect(() => {
    const prev = document.title
    document.title = 'Page not found | Mainspring'
    return () => { document.title = prev }
  }, [])
  return (
    <div className="min-h-screen bg-[#F7F5F0] text-[#1B2B3E]">
      <main className="mx-auto flex min-h-screen max-w-xl flex-col items-start justify-center px-5 py-10">
        <p className="text-sm font-semibold uppercase tracking-widest text-[#B8321E]">404</p>
        <h1 className="mt-2 text-3xl font-semibold">This page has wound down.</h1>
        <p className="mt-3 text-[15px] leading-7 text-[#5C6670]">
          The page you were looking for does not exist, or the link has moved. If you followed a link from a text or email, ask the shop to send it again.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/" className="inline-flex min-h-11 items-center rounded bg-[#B8321E] px-5 text-sm font-semibold text-white">Go to home</Link>
          <Link to="/login" className="inline-flex min-h-11 items-center rounded border border-[#1B2B3E] px-5 text-sm font-semibold">Log in</Link>
          <Link to="/customer-portal" className="inline-flex min-h-11 items-center rounded border border-[#1B2B3E] px-5 text-sm font-semibold">Track a repair</Link>
        </div>
        <p className="mt-8 text-sm text-[#5C6670]">Need a hand? <a className="underline" href="mailto:admin@mainspring.au">admin@mainspring.au</a></p>
      </main>
    </div>
  )
}
