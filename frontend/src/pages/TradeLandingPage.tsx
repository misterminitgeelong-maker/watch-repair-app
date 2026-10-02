import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { MKT, MARKETING_CSS } from '@/lib/marketingTheme'

const TRADES = {
  watch: {
    title: 'Watch repair management software Australia | Mainspring',
    heading: 'Watch repair management software for Australian shops',
    intro: 'Keep the counter and bench on the same page. Track each watch from intake photos and repair notes through quoting, customer approval, invoicing and collection.',
    steps: [
      ['Book the watch in', 'Keep customer details, watch photos and fault notes together on one repair ticket.'],
      ['Get the go-ahead', 'Send a quote approval link so the customer can review the proposed repair on their phone.'],
      ['Follow the repair', 'Keep job status and work notes with the ticket, so your team can see what needs attention.'],
      ['Invoice and collect', 'Prepare the invoice from the job and keep the repair record available after collection.'],
    ],
    questions: [
      ['Can I use it at the counter and at the bench?', 'Yes. Open Mainspring in the browser on a computer, tablet or phone using the same account.'],
      ['Does it support other repair trades?', 'Watch, shoe and mobile services are included, so a shop offering several trades can keep them in one system.'],
      ['How can I see the workflow first?', 'Open the interactive demo and try a watch repair ticket before starting your own shop account.'],
    ],
  },
  shoe: {
    title: 'Shoe repair management software Australia | Mainspring',
    heading: 'Shoe repair management software for Australian shops',
    intro: 'Replace the paper repair diary with a ticket your team can follow. Book shoe repairs, photograph the item, quote the work and track progress through to collection.',
    steps: [
      ['Book the repair', 'Record customer details, intake photos, fault notes and a collection date on the shoe repair ticket.'],
      ['Send the quote', 'Text the customer a quote approval link and keep their go-ahead attached to the job.'],
      ['See what is next', 'Follow jobs awaiting approval, in progress, completed and awaiting collection.'],
      ['Finish the ticket', 'Prepare an invoice from the repair and keep the customer and job history in one place.'],
    ],
    questions: [
      ['Can I attach photos of the shoes?', 'Yes. Keep intake photos on the repair ticket so staff can refer back to the item and its condition.'],
      ['Can a mixed repair shop use it?', 'Yes. The Shop plan includes shoe, watch and mobile services in one account.'],
      ['Do I need to install software on the shop computer?', 'No. Mainspring runs in the browser on computers, tablets and phones.'],
    ],
  },
} as const

export default function TradeLandingPage({ trade }: { trade: keyof typeof TRADES }) {
  const page = TRADES[trade]
  useEffect(() => {
    const previous = document.title
    document.title = page.title
    return () => { document.title = previous }
  }, [page.title])

  return (
    <div className="mkt-landing min-h-screen">
      <style>{MARKETING_CSS}</style>
      <header className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-6">
        <Link to="/" className="flex items-center gap-2" aria-label="Mainspring home">
          <img src="/marketing/mainspring-badge-vermilion.svg" alt="" width={34} height={34} />
          <span className="mkt-serif text-xl" style={{ color: MKT.ink }}>Mainspring</span>
        </Link>
        <Link to="/login" className="inline-flex min-h-11 items-center" style={{ color: MKT.ink }}>Log in</Link>
      </header>
      <main>
        <section style={{ background: MKT.oatmeal }}>
          <div className="mx-auto max-w-6xl px-5 py-14 sm:py-20">
            <p className="text-sm font-semibold" style={{ color: MKT.vermilionDeep }}>Australian-owned · Built in Geelong</p>
            <h1 className="mt-4 max-w-4xl text-4xl font-extrabold leading-tight sm:text-6xl" style={{ color: MKT.ink }}>{page.heading}</h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed" style={{ color: MKT.textBody }}>{page.intro}</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/signup" className="mkt-btn-primary inline-flex min-h-12 items-center px-6">Start a 14-day trial</Link>
              <Link to="/login?demo=1" className="mkt-btn-outline-ink inline-flex min-h-12 items-center px-6">Try the interactive demo</Link>
            </div>
            <p className="mt-4 text-sm" style={{ color: MKT.textBody }}>Shop plan A$50/month · Card required to start · Watch, shoe and mobile services included</p>
          </div>
        </section>
        <section className="mx-auto max-w-6xl px-5 py-14">
          <h2 className="text-3xl font-bold" style={{ color: MKT.ink }}>From intake to collection</h2>
          <div className="mt-7 grid gap-5 sm:grid-cols-2">
            {page.steps.map(([title, body], index) => (
              <article key={title} className="border p-6" style={{ borderColor: MKT.ruleMid, background: MKT.paper }}>
                <p className="text-sm font-bold" style={{ color: MKT.vermilionDeep }}>0{index + 1}</p>
                <h3 className="mt-3 text-xl font-bold" style={{ color: MKT.ink }}>{title}</h3>
                <p className="mt-3 leading-relaxed" style={{ color: MKT.textBody }}>{body}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="mx-auto max-w-6xl px-5 pb-14">
          <h2 className="text-3xl font-bold" style={{ color: MKT.ink }}>Questions from repair shops</h2>
          {page.questions.map(([question, answer]) => (
            <div key={question} className="mt-6 max-w-3xl">
              <h3 className="text-lg font-bold" style={{ color: MKT.ink }}>{question}</h3>
              <p className="mt-2 leading-relaxed" style={{ color: MKT.textBody }}>{answer}</p>
            </div>
          ))}
          <Link to="/pricing" className="mt-7 inline-flex min-h-11 items-center underline" style={{ color: MKT.vermilionDeep }}>Compare Shop and Pro plans</Link>
        </section>
      </main>
      <footer className="border-t px-5 py-7" style={{ borderColor: MKT.ruleMid }}>
        <nav className="mx-auto flex max-w-6xl flex-wrap gap-x-6 gap-y-2" aria-label="Explore Mainspring">
          {[
            ['/', 'All trades'], ['/watch-repair-software', 'Watch repair software'],
            ['/shoe-repair-software', 'Shoe repair software'], ['/mobile-services', 'Mobile locksmith software'],
            ['/pricing', 'Pricing'], ['/privacy', 'Privacy'],
          ].map(([path, label]) => <Link key={path} to={path} className="inline-flex min-h-11 items-center underline" style={{ color: MKT.textBody }}>{label}</Link>)}
          <a href="mailto:admin@mainspring.au" className="inline-flex min-h-11 items-center underline" style={{ color: MKT.textBody }}>Contact us</a>
        </nav>
      </footer>
    </div>
  )
}
