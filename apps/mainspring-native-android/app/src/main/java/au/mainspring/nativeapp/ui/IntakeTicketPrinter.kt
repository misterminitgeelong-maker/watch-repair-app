package au.mainspring.nativeapp.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.PageRange
import android.print.PrintAttributes
import android.print.PrintDocumentAdapter
import android.print.PrintDocumentInfo
import android.print.PrintManager
import java.io.FileOutputStream

enum class IntakeTicketKind(val label: String, val statusPath: String) {
    WATCH("Repair", "customer-portal/job/watch"),
    SHOE("Shoe repair", "shoe-status"),
}

data class IntakeTicket(
    val jobNumber: String,
    val customerName: String?,
    val customerPhone: String?,
    val itemSummary: String,
    val workSummary: String?,
    val dueDate: String?,
    val deposit: String?,
    val statusUrl: String,
    val shopName: String?,
    val shopPhone: String?,
    val kind: IntakeTicketKind,
    val workshopUrl: String? = null,
    val dateIn: String? = null,
    val status: String? = null,
    val priority: String? = null,
    val salesperson: String? = null,
    val customerEmail: String? = null,
    val serial: String? = null,
    val movement: String? = null,
    val condition: String? = null,
    val services: String? = null,
    val estimate: String? = null,
    val balance: String? = null,
)

/** Public customer status link: `<api origin>/status/<token>` (watch) or `/shoe-status/<token>` (shoe). */
fun intakeStatusUrl(apiBaseUrl: String, kind: IntakeTicketKind, token: String): String {
    val uri = try { java.net.URI(apiBaseUrl.trim()) } catch (e: Exception) { null }
    val origin = if (uri?.scheme != null && uri.host != null) "${uri.scheme}://${uri.host}" + (if (uri.port != -1) ":${uri.port}" else "") else apiBaseUrl.trimEnd('/')
    return "$origin/${kind.statusPath}/$token"
}

/** One printable copy of the ticket: a title, a subtitle, labelled rows and a closing note. */
data class IntakeTicketCopy(val title: String, val subtitle: String, val rows: List<Pair<String, String>>, val qrCaption: String)

fun intakeTicketCopies(t: IntakeTicket): List<IntakeTicketCopy> {
    fun dash(v: String?) = v?.takeIf { it.isNotBlank() } ?: "—"
    val shared = listOf("Ticket #" to t.jobNumber, "Item" to t.itemSummary.ifBlank { "—" }) + listOfNotNull(t.dateIn?.let { "Date in" to it })
    val workshop = IntakeTicketCopy(
        "${t.kind.label} intake ticket", "Internal copy for workshop",
        shared + (if(t.kind == IntakeTicketKind.WATCH) listOf("Status" to dash(t.status), "Priority" to dash(t.priority), "Salesperson" to dash(t.salesperson)) else emptyList()) +
            listOf("Customer" to dash(t.customerName), "Phone" to dash(t.customerPhone)) +
            (if(t.kind == IntakeTicketKind.WATCH) listOf("Email" to dash(t.customerEmail), "Serial" to dash(t.serial), "Movement" to dash(t.movement), "Condition notes" to dash(t.condition)) else emptyList()) + listOfNotNull(t.services?.let { "Services" to it }) +
            listOf("Work requested" to dash(t.workSummary), "Due" to dash(t.dueDate), "Deposit" to dash(t.deposit)) + listOfNotNull(t.estimate?.let { "Estimate" to it }),
        if(t.workshopUrl != null) "Open internal ticket" else "Scan for repair status",
    )
    val customer = IntakeTicketCopy(
        "Customer intake copy", "Keep this ticket for pickup and updates",
        shared + listOfNotNull("Work requested" to dash(t.services ?: t.workSummary), "Due" to (t.dueDate?.takeIf { it.isNotBlank() } ?: "TBC"),
            t.estimate?.let { "Estimated repair" to it },
            t.deposit?.takeIf { it.isNotBlank() }?.let { "Deposit paid" to it },
            t.balance?.let { "Estimated balance" to it },
            listOfNotNull(t.shopName, t.shopPhone).joinToString(" · ").takeIf { it.isNotBlank() }?.let { "Shop" to it }),
        "Scan for live repair updates",
    )
    return listOf(workshop, customer)
}

fun printIntakeTicket(context: Context, ticket: IntakeTicket) = printIntakeTickets(context, listOf(ticket))

/** One print job with two pages (workshop, customer) per ticket, so a multi-watch intake prints in one go. */
fun printIntakeTickets(context: Context, tickets: List<IntakeTicket>) {
    require(tickets.isNotEmpty()) { "Nothing to print." }
    val manager = context.getSystemService(Context.PRINT_SERVICE) as? PrintManager ?: error("Printing is unavailable on this device.")
    manager.print(if (tickets.size == 1) "Ticket ${tickets[0].jobNumber}" else "Tickets ${tickets.joinToString(", ") { it.jobNumber }}", IntakeTicketAdapter(tickets), PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).build())
}

private class IntakeTicketAdapter(private val tickets: List<IntakeTicket>) : PrintDocumentAdapter() {
    private val sheets = tickets.flatMap { t -> intakeTicketCopies(t).flatMapIndexed { index, copy ->
        paginateIntakeCopy(copy).map { it to if(index == 0) t.workshopUrl ?: t.statusUrl else t.statusUrl }
    } }


    override fun onLayout(oldAttributes: PrintAttributes?, newAttributes: PrintAttributes, cancellationSignal: CancellationSignal, callback: LayoutResultCallback, extras: Bundle?) {
        if (cancellationSignal.isCanceled) { callback.onLayoutCancelled(); return }
        callback.onLayoutFinished(PrintDocumentInfo.Builder("intake-ticket-${tickets[0].jobNumber}.pdf").setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT).setPageCount(sheets.size).build(), oldAttributes != newAttributes)
    }

    override fun onWrite(pages: Array<out PageRange>, destination: ParcelFileDescriptor, cancellationSignal: CancellationSignal, callback: WriteResultCallback) {
        val pdf = PdfDocument()
        try {
            sheets.forEachIndexed { i, (copy, url) ->
                if (cancellationSignal.isCanceled) { callback.onWriteCancelled(); return }
                if(pages.none { i in it.start..it.end }) return@forEachIndexed
                val page = pdf.startPage(PdfDocument.PageInfo.Builder(595, 842, i + 1).create())
                drawIntakeCopy(page.canvas, copy, QrCode.encode(url))
                pdf.finishPage(page)
            }
            FileOutputStream(destination.fileDescriptor).use { pdf.writeTo(it) }
            callback.onWriteFinished(pages)
        } catch (e: Exception) {
            callback.onWriteFailed(e.message)
        } finally { pdf.close() }
    }
}

/** Keep all intake detail, splitting long notes over continuation sheets before they reach the QR area. */
internal fun paginateIntakeCopy(copy: IntakeTicketCopy): List<IntakeTicketCopy> {
    val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 13f }
    val titlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 24f; typeface = Typeface.DEFAULT_BOLD }
    val subtitlePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 11f }
    // Reserve space for the longest continuation subtitle as well as the QR and lower margin.
    val header = 62 + wrapText(copy.title, titlePaint, 515f).size * 28 + wrapText(copy.subtitle + " · continued 9999", subtitlePaint, 515f).size * 16 + 26
    val budget = minOf(450, 800 - 180 - 20 - header).coerceAtLeast(100)
    val rows = copy.rows.flatMap { (label, value) ->
        wrapText(value, paint, 385f).chunked(12).mapIndexed { index, lines -> (if(index == 0) label else "$label (cont.)") to lines.joinToString("\n") }
    }
    val groups = mutableListOf<MutableList<Pair<String, String>>>()
    var height = 0
    for(row in rows) {
        val next = maxOf(1, wrapText(row.second, paint, 385f).size) * 17 + 10
        if(groups.isEmpty() || height + next > budget) { groups.add(mutableListOf()); height = 0 }
        groups.last().add(row); height += next
    }
    return groups.mapIndexed { index, page -> copy.copy(subtitle = copy.subtitle + if(index == 0) "" else " · continued ${index + 1}", rows = page) }
}

internal fun drawIntakeCopy(canvas: Canvas, copy: IntakeTicketCopy, qr: Array<BooleanArray>) {
    val left = 40f; val right = 555f
    val ink = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.BLACK }
    val muted = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.DKGRAY; textSize = 11f }
    val title = Paint(ink).apply { textSize = 24f; typeface = Typeface.DEFAULT_BOLD }
    val label = Paint(ink).apply { textSize = 11f; typeface = Typeface.DEFAULT_BOLD }
    val value = Paint(ink).apply { textSize = 13f }
    val rule = Paint().apply { color = Color.LTGRAY; strokeWidth = 1f }
    var y = 62f
    wrapText(copy.title, title, right - left).forEach { canvas.drawText(it, left, y, title); y += 28f }
    wrapText(copy.subtitle, muted, right - left).forEach { canvas.drawText(it, left, y, muted); y += 16f }
    y += 4f
    canvas.drawLine(left, y, right, y, rule); y += 22f
    for ((k, v) in copy.rows) {
        canvas.drawText(k.uppercase(), left, y, label)
        val lines = wrapText(v, value, right - (left + 130f))
        lines.forEachIndexed { i, line -> canvas.drawText(line, left + 130f, y + i * 17f, value) }
        y += maxOf(1, lines.size) * 17f + 10f
        canvas.drawLine(left, y - 12f, right, y - 12f, rule)
    }
    y += 20f
    val quiet = 4
    val side = 180f
    val cell = side / (qr.size + quiet * 2)
    canvas.drawRect(left, y, left + side, y + side, Paint().apply { color = Color.WHITE })
    val dark = Paint().apply { color = Color.BLACK }
    for (r in qr.indices) for (c in qr.indices) if (qr[r][c]) {
        val x = left + (c + quiet) * cell; val yy = y + (r + quiet) * cell
        canvas.drawRect(x, yy, x + cell, yy + cell, dark)
    }
    canvas.drawText(copy.qrCaption, left + side + 16f, y + side / 2, muted)
}

internal fun wrapText(text: String, paint: Paint, width: Float): List<String> {
    val out = ArrayList<String>()
    for (para in text.split('\n')) {
        var line = ""
        for (word in para.split(' ')) {
            if(paint.measureText(word) > width) {
                if(line.isNotEmpty()) { out.add(line); line = "" }
                var remaining = word
                while(remaining.isNotEmpty()) {
                    val count = paint.breakText(remaining, true, width, null).coerceAtLeast(1)
                    if(count == remaining.length) { line = remaining; break }
                    out.add(remaining.take(count)); remaining = remaining.drop(count)
                }
                continue
            }
            val candidate = if (line.isEmpty()) word else "$line $word"
            if (line.isNotEmpty() && paint.measureText(candidate) > width) { out.add(line); line = word } else line = candidate
        }
        out.add(line)
    }
    return out
}
