package au.mainspring.nativeapp.ui

import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import au.mainspring.nativeapp.niimbot.NiimbotLabelData
import au.mainspring.nativeapp.niimbot.niimbotBalanceCents
import au.mainspring.nativeapp.niimbot.niimbotJobLabels

/** Everything needed to print one job: the A4 ticket (PrintManager) and its two Niimbot labels. */
data class JobPrintBundle(val ticket: IntakeTicket, val labels: List<NiimbotLabelData>)

/** Shop details that stay constant across the jobs of one print run. */
data class JobPrintContext(
    val apiBaseUrl: String,
    val shopName: String?,
    val shopPhone: String?,
    val money: (Int) -> String,
    val date: (String) -> String,
)

fun watchJobBundle(job: RepairJobRead, ctx: JobPrintContext): JobPrintBundle? {
    val token = job.statusToken ?: return null
    val item = listOfNotNull(job.watchBrand, job.watchModel).joinToString(" ").ifBlank { "Watch" }
    val url = intakeStatusUrl(ctx.apiBaseUrl, IntakeTicketKind.WATCH, token)
    val ticket = IntakeTicket(
        jobNumber = job.jobNumber, customerName = job.customerName, customerPhone = job.customerPhone, itemSummary = item,
        workSummary = listOfNotNull(job.title.takeIf { it.isNotBlank() }, job.description?.takeIf { it.isNotBlank() }).joinToString("\n").ifBlank { null },
        dueDate = job.collectionDate?.takeIf { it.isNotBlank() }?.let(ctx.date),
        deposit = job.depositCents.takeIf { it > 0 }?.let(ctx.money),
        statusUrl = url, shopName = ctx.shopName, shopPhone = ctx.shopPhone, kind = IntakeTicketKind.WATCH,
    )
    val base = NiimbotLabelData(
        jobNumber = job.jobNumber, customerName = job.customerName, customerPhone = job.customerPhone, itemTitle = item,
        services = job.title.takeIf { it.isNotBlank() }, dateIn = job.createdAt.takeIf { it.isNotBlank() }?.let(ctx.date), qrText = url,
    )
    val balance = niimbotBalanceCents(job.costCents, job.preQuoteCents, job.depositCents)
    return JobPrintBundle(ticket, niimbotJobLabels(base, ctx.money(job.depositCents), ctx.money(balance)))
}

fun shoeJobBundle(j: ShoeRepairJobRead, customerName: String?, customerPhone: String?, ctx: JobPrintContext): JobPrintBundle {
    val pairs = listOfNotNull(j.shoe) + j.extraShoes.orEmpty().mapNotNull { it.shoe }
    val item = pairs.joinToString("; ") { listOfNotNull(it.brand, it.shoeType, it.color).joinToString(" ") }.ifBlank { j.title }
    val url = intakeStatusUrl(ctx.apiBaseUrl, IntakeTicketKind.SHOE, j.statusToken)
    val ticket = IntakeTicket(
        jobNumber = j.jobNumber, customerName = customerName, customerPhone = customerPhone, itemSummary = item,
        workSummary = (j.items.map { it.name } + listOfNotNull(j.description?.takeIf { it.isNotBlank() })).joinToString("\n").ifBlank { j.title },
        dueDate = j.collectionDate?.takeIf { it.isNotBlank() }?.let(ctx.date),
        deposit = j.depositCents.takeIf { it > 0 }?.let(ctx.money),
        statusUrl = url, shopName = ctx.shopName, shopPhone = ctx.shopPhone, kind = IntakeTicketKind.SHOE,
    )
    val base = NiimbotLabelData(
        jobNumber = j.jobNumber, customerName = customerName, customerPhone = customerPhone, itemTitle = item,
        services = j.items.firstOrNull()?.name ?: j.title.takeIf { it.isNotBlank() }, dateIn = ctx.date(j.createdAt), qrText = url,
    )
    val balance = niimbotBalanceCents(j.costCents, 0, j.depositCents)
    return JobPrintBundle(ticket, niimbotJobLabels(base, ctx.money(j.depositCents), ctx.money(balance)))
}
