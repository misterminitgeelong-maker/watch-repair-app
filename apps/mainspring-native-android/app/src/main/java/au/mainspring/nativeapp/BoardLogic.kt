package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AccountInvoice
import au.mainspring.nativeapp.api.CustomerOrderRead
import au.mainspring.nativeapp.api.ProspectLead
import au.mainspring.nativeapp.ui.screens.BoardCard
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** "Added dd/MM/yyyy" for the customer list, in the shop timezone; blank when the timestamp cannot be read. */
fun customerAddedLabel(createdAt: String?, zone: String): String {
    val raw = createdAt?.trim().orEmpty()
    if(raw.isEmpty()) return ""
    val date = try {
        if(raw.length == 10) LocalDate.parse(raw)
        else (try { OffsetDateTime.parse(raw).toInstant() } catch(_: Exception) { LocalDateTime.parse(raw).toInstant(java.time.ZoneOffset.UTC) }).atZone(ZoneId.of(zone)).toLocalDate()
    } catch(_: Exception) { return "" }
    return "Added " + date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))
}

private fun csvCell(value: Any?): String {
    val text = value?.toString().orEmpty()
    return if(text.any { it == ',' || it == '"' || it == '\n' || it == '\r' }) "\"" + text.replace("\"", "\"\"") + "\"" else text
}

/** Same columns as the web account page's "Export CSV"; one row per invoice line, or one row for a line-less invoice. */
fun accountInvoicesCsv(invoices: List<AccountInvoice>): String {
    val rows = mutableListOf(listOf("invoice_number", "period_year", "period_month", "status", "subtotal_cents", "tax_cents", "total_cents",
        "source_type", "job_number", "description", "line_amount_cents", "created_at").joinToString(",") { csvCell(it) })
    for(i in invoices) {
        val head = listOf(i.number, i.year, i.month, i.status, i.subtotal, i.tax, i.total)
        if(i.lines.isEmpty()) rows += (head + listOf("", "", "", "", i.createdAt.orEmpty())).joinToString(",") { csvCell(it) }
        else i.lines.forEach { l -> rows += (head + listOf(l.sourceType, l.jobNumber, l.description, l.amount, i.createdAt.orEmpty())).joinToString(",") { csvCell(it) } }
    }
    return rows.joinToString("\n")
}

fun accountInvoicesCsvFileName(accountName: String): String =
    (accountName.lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-').ifEmpty { "customer-account" }) + "-invoices.csv"

fun customerOrderCards(orders: List<CustomerOrderRead>): List<BoardCard> = orders.map {
    BoardCard(it.id, it.title, listOfNotNull(it.customerName?.takeIf { n -> n.isNotBlank() }, it.supplier?.takeIf { s -> s.isNotBlank() }).joinToString(" · "), it.status)
}

/** Prospect board stages in web order. */
val PROSPECT_STAGES = listOf("new" to "New business", "contacted" to "Business contacted", "visited" to "Business visited", "onboarded" to "Business onboarded",
    "quote_needed" to "Quote needed", "follow_up_due" to "Follow-up due", "won" to "Won", "lost" to "Archived")

/** The only stage move the backend supports (POST advance); null when the prospect cannot be advanced. */
fun prospectNextStage(status: String): String? = when(status) {
    "new", "quote_needed", "follow_up_due" -> "contacted"; "contacted" -> "visited"; "visited" -> "onboarded"; else -> null
}

fun prospectCards(leads: List<ProspectLead>): List<BoardCard> = leads.map {
    BoardCard(it.id, it.name, listOfNotNull(it.contactName?.takeIf { n -> n.isNotBlank() }, it.phone?.takeIf { p -> p.isNotBlank() }).joinToString(" · "), it.status)
}
