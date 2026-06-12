import type { SlaChip, SlaChipKind } from './dispatchHelpers'

const SLA_CHIP_STYLES: Record<SlaChipKind, { backgroundColor: string; color: string }> = {
  late: { backgroundColor: 'rgba(201,100,90,0.15)', color: '#C96A5A' },
  at_risk: { backgroundColor: 'rgba(200,130,50,0.16)', color: '#B87030' },
  aging: { backgroundColor: 'rgba(138,117,99,0.2)', color: '#7A6453' },
}

export function SlaChipBadge({ chip }: { chip: SlaChip }) {
  return (
    <span
      className="text-[11px] font-bold uppercase rounded-full px-2 py-0.5"
      style={SLA_CHIP_STYLES[chip.kind]}
    >
      {chip.label}
    </span>
  )
}
