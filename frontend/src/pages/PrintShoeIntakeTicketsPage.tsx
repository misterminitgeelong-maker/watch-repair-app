import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bluetooth, BluetoothOff, ChevronLeft, Printer } from 'lucide-react'
import QRCode from 'qrcode'
import { getCustomer, getShoeRepairJob, type ShoeRepairJobItem, type Shoe } from '@/lib/api'
import { Spinner } from '@/components/ui'
import { formatDate } from '@/lib/utils'
import { renderShoeLabel } from '@/lib/niimbot'
import { useNiimbotPrinter } from '@/hooks/useNiimbotPrinter'

function formatCents(value: number) {
  return (value / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function shoeLabel(shoe: Shoe | undefined): string {
  if (!shoe) return 'Pair'
  const parts = [shoe.brand, shoe.shoe_type, shoe.color].filter(Boolean)
  return parts.join(' · ') || 'Pair'
}

export default function PrintShoeIntakeTicketsPage() {
  const { id } = useParams<{ id: string }>()
  const [params] = useSearchParams()
  const autoPrint = params.get('autoprint') === '1'
  const [repairQr, setRepairQr] = useState('')
  const [customerQr, setCustomerQr] = useState('')
  const { status: btStatus, errorMessage: btError, isSupported: btSupported, labelDots, connect: btConnect, autoConnect: btAutoConnect, disconnect: btDisconnect, print: btPrint } = useNiimbotPrinter()
  const [autoTriedBt, setAutoTriedBt] = useState(false)
  const [labelCanvases, setLabelCanvases] = useState<HTMLCanvasElement[] | null>(null)
  const [labelPreviews, setLabelPreviews] = useState<string[]>([])

  const { data: job, isLoading } = useQuery({
    queryKey: ['shoe-repair-job', id],
    queryFn: () => getShoeRepairJob(id!).then(r => r.data),
    enabled: !!id,
  })

  const { data: customer } = useQuery({
    queryKey: ['customer', job?.shoe?.customer_id],
    queryFn: () => getCustomer(job!.shoe!.customer_id).then(r => r.data),
    enabled: !!job?.shoe?.customer_id,
  })

  const total = useMemo(() => {
    if (!job) return 0
    return job.items.reduce((sum, item) => sum + (item.unit_price_cents != null ? item.unit_price_cents * item.quantity : 0), 0)
  }, [job])

  const balance = Math.max(total - (job?.deposit_cents || 0), 0)

  useEffect(() => {
    if (!job) return
    const internalUrl = `${window.location.origin}/shoe-repairs/${job.id}`
    const customerUrl = `${window.location.origin}/shoe-status/${job.status_token}`
    QRCode.toDataURL(internalUrl, { width: 300, margin: 1 }).then(setRepairQr)
    QRCode.toDataURL(customerUrl, { width: 300, margin: 1 }).then(setCustomerQr)
  }, [job])

  // Pre-render canvases when data is ready
  useEffect(() => {
    if (!job || !customer || !repairQr || !customerQr) return
    const shoes = [job.shoe, ...job.extra_shoes.map(e => e.shoe)]
    const shoeDescription = shoes.map(s => shoeLabel(s)).join(', ')
    const shared = {
      jobNumber: job.job_number,
      customerName: customer.full_name || '—',
      customerPhone: customer.phone || undefined,
      shoeDescription,
      dateIn: formatDate(job.created_at),
    }
    Promise.all([
      renderShoeLabel({ ...shared, qrDataUrl: repairQr, isCustomerCopy: false, depositLabel: formatCents(job.deposit_cents || 0), balanceLabel: formatCents(balance), labelDots: labelDots ?? undefined }),
      renderShoeLabel({ ...shared, qrDataUrl: customerQr, isCustomerCopy: true, labelDots: labelDots ?? undefined }),
    ]).then(([workshopCanvas, customerCanvas]) => {
      setLabelCanvases([workshopCanvas, customerCanvas])
      setLabelPreviews([workshopCanvas.toDataURL(), customerCanvas.toDataURL()])
    })
  }, [job, customer, repairQr, customerQr, balance, labelDots])

  useEffect(() => {
    if (!autoPrint || !job || !repairQr || !customerQr || autoTriedBt) return
    setAutoTriedBt(true)
    if (btSupported) {
      btAutoConnect().then(connected => {
        if (connected) printToNiimbot()
      })
    } else {
      const t = window.setTimeout(() => window.print(), 250)
      return () => window.clearTimeout(t)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPrint, job, repairQr, customerQr])

  const printToNiimbot = useCallback(async () => {
    if (!labelCanvases) return
    await btPrint(labelCanvases)
  }, [labelCanvases, btPrint])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    )
  }
  if (!job) return <p className="p-8" style={{ color: 'var(--ms-text-muted)' }}>Job not found.</p>

  const allShoes = [job.shoe, ...job.extra_shoes.map(e => e.shoe)]

  return (
    <>
      <div className="print:hidden fixed top-0 left-0 right-0 px-6 py-3 flex items-center justify-between z-10 shadow-sm" style={{ backgroundColor: 'var(--ms-surface)', borderBottom: '1px solid var(--ms-border)' }}>
        <Link
          to={`/shoe-repairs/${id}`}
          className="inline-flex items-center gap-1 text-sm font-medium transition-colors"
          style={{ color: 'var(--ms-text-muted)' }}
        >
          <ChevronLeft size={15} /> Back
        </Link>
        <div className="flex items-center gap-2">
          {btSupported && (
            btStatus === 'connected' || btStatus === 'printing' ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={printToNiimbot}
                  disabled={btStatus === 'printing' || !labelCanvases}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                  style={{ backgroundColor: '#1d6b3e', color: '#fff' }}
                >
                  <Bluetooth size={15} />
                  {btStatus === 'printing' ? 'Printing…' : 'Print to M2'}
                </button>
                <button
                  onClick={btDisconnect}
                  className="p-2 rounded-lg transition-colors"
                  title="Disconnect printer"
                  style={{ color: 'var(--ms-text-muted)' }}
                >
                  <BluetoothOff size={15} />
                </button>
              </div>
            ) : (
              <button
                onClick={btConnect}
                disabled={btStatus === 'connecting'}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
              >
                <Bluetooth size={15} />
                {btStatus === 'connecting' ? 'Connecting…' : 'Connect M2'}
              </button>
            )
          )}
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            style={{ backgroundColor: 'var(--ms-accent)', color: '#FEFCF8' }}
          >
            <Printer size={15} /> Print / PDF
          </button>
        </div>
      </div>
      {btError && (
        <div className="print:hidden fixed top-14 left-0 right-0 px-6 py-2 text-sm text-center" style={{ backgroundColor: '#fef2f2', color: '#991b1b', borderBottom: '1px solid #fecaca' }}>
          Printer error: {btError}
        </div>
      )}

      {autoPrint && btSupported && btStatus !== 'printing' && (
        <div className="print:hidden fixed bottom-0 left-0 right-0 p-4 z-20 sm:hidden" style={{ backgroundColor: 'var(--ms-surface)', borderTop: '1px solid var(--ms-border)' }}>
          {btStatus === 'connected' ? (
            <button
              onClick={printToNiimbot}
              disabled={!labelCanvases}
              className="w-full flex items-center justify-center gap-3 py-4 rounded-xl text-base font-bold disabled:opacity-50"
              style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
            >
              <Bluetooth size={22} /> Print 2 Labels to M2
            </button>
          ) : btStatus === 'connecting' ? (
            <div className="w-full flex items-center justify-center gap-3 py-4 rounded-xl text-base font-semibold" style={{ backgroundColor: 'var(--ms-border)', color: 'var(--ms-text)' }}>
              <Spinner /> Connecting to M2…
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <button
                onClick={btConnect}
                className="w-full flex items-center justify-center gap-3 py-4 rounded-xl text-base font-bold"
                style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
              >
                <Bluetooth size={22} /> Connect M2 &amp; Print
              </button>
              <button onClick={() => window.print()} className="w-full py-2 text-sm text-center" style={{ color: 'var(--ms-text-muted)' }}>
                Print / PDF instead
              </button>
            </div>
          )}
        </div>
      )}

      <div className={`print:pt-0 pt-16 min-h-screen bg-[#F8F4EE] print:bg-white${autoPrint && btSupported ? ' pb-28 sm:pb-0' : ''}`}>
        <div className="max-w-3xl mx-auto py-8 print:py-0 space-y-6 print:space-y-0">

          {labelPreviews.length > 0 && (
            <div className="print:hidden bg-white rounded-xl shadow-lg p-4">
              <p className="text-xs font-medium mb-3" style={{ color: 'var(--ms-text-muted)' }}>LABEL PREVIEW</p>
              <div className="flex gap-4 overflow-x-auto">
                {labelPreviews.map((src, i) => (
                  <div key={i} className="shrink-0 text-center">
                    <img src={src} alt={`Label ${i + 1}`} className="h-24 rounded" style={{ border: '1px solid var(--ms-border)', imageRendering: 'pixelated' }} />
                    <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>{i === 0 ? 'Workshop' : 'Customer'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <section className="bg-white shadow-lg print:shadow-none rounded-xl print:rounded-none p-8 print:p-6 print:break-after-page">
            <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--ms-text)' }}>Repair Intake Ticket</h1>
            <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)' }}>Internal copy for workshop</p>

            <div className="grid grid-cols-2 gap-4 text-sm mb-4">
              <div><strong>Ticket #:</strong> {job.job_number}</div>
              <div><strong>Date In:</strong> {formatDate(job.created_at)}</div>
              <div><strong>Status:</strong> {job.status.replace(/_/g, ' ')}</div>
              <div><strong>Priority:</strong> {job.priority}</div>
              <div><strong>Salesperson:</strong> {job.salesperson || '—'}</div>
              <div><strong>Collection:</strong> {job.collection_date || '—'}</div>
            </div>

            <div className="rounded-lg p-3 mb-4" style={{ border: '1px solid var(--ms-border)' }}>
              <p><strong>Customer:</strong> {customer?.full_name || '—'}</p>
              <p><strong>Phone:</strong> {customer?.phone || '—'}</p>
              <p><strong>Email:</strong> {customer?.email || '—'}</p>
            </div>

            <div className="rounded-lg p-3 mb-4" style={{ border: '1px solid var(--ms-border)' }}>
              <p className="font-semibold mb-1">Pairs in this ticket</p>
              <ul className="list-disc pl-5">
                {allShoes.map((shoe, idx) => (
                  <li key={idx}>{shoeLabel(shoe)}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-lg p-3 mb-4" style={{ border: '1px solid var(--ms-border)' }}>
              <p className="font-semibold mb-1">Workshop notes</p>
              <p className="whitespace-pre-wrap">{job.description || '—'}</p>
            </div>

            <div className="rounded-lg p-3 mb-4" style={{ border: '1px solid var(--ms-border)' }}>
              <p className="font-semibold mb-2">Selected services</p>
              {job.items.length === 0 ? (
                <p>—</p>
              ) : (
                <ul className="space-y-1">
                  {job.items.map((item: ShoeRepairJobItem) => (
                    <li key={item.id} className="text-sm">
                      {item.item_name}
                      {item.quantity > 1 ? ` x ${item.quantity}` : ''}
                      {item.notes ? ` - ${item.notes}` : ''}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="flex justify-between items-end gap-4">
              <div className="text-sm">
                <p><strong>Deposit:</strong> {formatCents(job.deposit_cents)}</p>
                <p><strong>Estimate:</strong> {formatCents(total)}</p>
              </div>
              {repairQr && (
                <div className="text-center">
                  <img src={repairQr} alt="Repair ticket QR" className="w-28 h-28" />
                  <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Open internal ticket</p>
                </div>
              )}
            </div>
          </section>

          <section className="bg-white shadow-lg print:shadow-none rounded-xl print:rounded-none p-8 print:p-6">
            <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--ms-text)' }}>Customer Intake Copy</h1>
            <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)' }}>Keep this ticket for pickup and updates</p>

            <div className="grid grid-cols-2 gap-4 text-sm mb-4">
              <div><strong>Ticket #:</strong> {job.job_number}</div>
              <div><strong>Date In:</strong> {formatDate(job.created_at)}</div>
              <div><strong>Pairs:</strong> {allShoes.length}</div>
              <div><strong>Collection:</strong> {job.collection_date || 'TBC'}</div>
            </div>

            <div className="rounded-lg p-3 mb-4" style={{ border: '1px solid var(--ms-border)' }}>
              <p className="font-semibold mb-2">Price Breakdown</p>
              {job.items.length > 0 ? (
                <div className="space-y-1 text-sm">
                  {job.items.map(item => {
                    const lineTotal = item.unit_price_cents != null ? item.unit_price_cents * item.quantity : null
                    return (
                      <div key={item.id} className="flex justify-between gap-4">
                        <span>{item.item_name}{item.quantity > 1 ? ` x ${item.quantity}` : ''}</span>
                        <span>{lineTotal == null ? 'Quoted' : formatCents(lineTotal)}</span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="text-sm">No priced services selected yet.</p>
              )}
              <div className="flex justify-between text-sm mt-3"><span>Subtotal estimate</span><span>{formatCents(total)}</span></div>
              <div className="flex justify-between text-sm"><span>Deposit paid</span><span>- {formatCents(job.deposit_cents)}</span></div>
              <div className="flex justify-between text-sm font-semibold mt-2 pt-2" style={{ borderTop: '1px solid var(--ms-border)' }}>
                <span>Estimated balance</span><span>{formatCents(balance)}</span>
              </div>
            </div>

            <div className="flex justify-between items-end gap-4">
              <div className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>
                Scan for live repair updates.
              </div>
              {customerQr && (
                <div className="text-center">
                  <img src={customerQr} alt="Customer status QR" className="w-28 h-28" />
                  <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Track this repair</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>

      <style>{`
        @media print {
          @page { margin: 0.35in; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>
    </>
  )
}
