export interface PosReceiptLine {
  description: string
  quantity: number
  unit_price_cents: number
}

export interface PosReceiptSale {
  invoiceNumber: string
  customerName: string
  lines: PosReceiptLine[]
  subtotalCents: number
  taxCents: number
  totalCents: number
  completedAt: Date
}

function money(cents: number) {
  return `$${(cents / 100).toFixed(2)}`
}

/**
 * Formatted for an 80mm thermal receipt roll (e.g. SAM4S). Print via
 * window.print() — the browser's OS printer driver handles the ESC/POS
 * translation, so this only needs to lay out cleanly at ~72mm content width.
 */
export function PosReceipt({ sale, shopName, shopAddress }: { sale: PosReceiptSale; shopName: string | null; shopAddress: string | null }) {
  return (
    <>
      <div id="pos-receipt" className="mx-auto bg-white text-black" style={{ width: '80mm', padding: '4mm', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
        <div className="text-center mb-3">
          <p className="text-sm font-bold uppercase">{shopName || 'Receipt'}</p>
          {shopAddress && <p className="text-[10px] mt-0.5">{shopAddress}</p>}
        </div>
        <div className="text-[11px] mb-2 border-t border-b border-dashed border-black py-1.5">
          <div className="flex justify-between"><span>Invoice</span><span>{sale.invoiceNumber}</span></div>
          <div className="flex justify-between"><span>Date</span><span>{sale.completedAt.toLocaleString('en-AU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}</span></div>
          <div className="flex justify-between"><span>Customer</span><span>{sale.customerName}</span></div>
        </div>
        <div className="text-[11px] mb-2">
          {sale.lines.map((line, i) => (
            <div key={i} className="mb-1">
              <div className="flex justify-between"><span>{line.description}</span><span>{money(line.quantity * line.unit_price_cents)}</span></div>
              {line.quantity > 1 && <div className="text-[10px] opacity-70">{line.quantity} × {money(line.unit_price_cents)}</div>}
            </div>
          ))}
        </div>
        <div className="text-[11px] border-t border-dashed border-black pt-1.5">
          <div className="flex justify-between"><span>Subtotal</span><span>{money(sale.subtotalCents)}</span></div>
          {sale.taxCents > 0 && <div className="flex justify-between"><span>Tax</span><span>{money(sale.taxCents)}</span></div>}
          <div className="flex justify-between text-sm font-bold mt-1"><span>Total</span><span>{money(sale.totalCents)}</span></div>
        </div>
        <p className="text-center text-[10px] mt-3">Thank you!</p>
      </div>
      <style>{`
        @media print {
          @page { size: 80mm auto; margin: 0; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>
    </>
  )
}
