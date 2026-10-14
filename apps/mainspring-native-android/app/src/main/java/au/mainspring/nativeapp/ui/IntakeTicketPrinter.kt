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
    WATCH("Repair", "status"),
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
    val shared = listOf("Ticket #" to t.jobNumber, "Item" to t.itemSummary.ifBlank { "—" })
    val workshop = IntakeTicketCopy(
        "${t.kind.label} intake ticket", "Internal copy for workshop",
        shared + listOf("Customer" to dash(t.customerName), "Phone" to dash(t.customerPhone), "Work requested" to dash(t.workSummary),
            "Due" to dash(t.dueDate), "Deposit" to dash(t.deposit)),
        "Scan for repair status",
    )
    val customer = IntakeTicketCopy(
        "Customer intake copy", "Keep this ticket for pickup and updates",
        shared + listOfNotNull("Work requested" to dash(t.workSummary), "Due" to (t.dueDate?.takeIf { it.isNotBlank() } ?: "TBC"),
            t.deposit?.takeIf { it.isNotBlank() }?.let { "Deposit paid" to it },
            listOfNotNull(t.shopName, t.shopPhone).joinToString(" · ").takeIf { it.isNotBlank() }?.let { "Shop" to it }),
        "Scan for live repair updates",
    )
    return listOf(workshop, customer)
}

fun printIntakeTicket(context: Context, ticket: IntakeTicket) {
    val manager = context.getSystemService(Context.PRINT_SERVICE) as? PrintManager ?: error("Printing is unavailable on this device.")
    manager.print("Ticket ${ticket.jobNumber}", IntakeTicketAdapter(ticket), PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).build())
}

private class IntakeTicketAdapter(private val ticket: IntakeTicket) : PrintDocumentAdapter() {
    private val copies = intakeTicketCopies(ticket)
    private val qr by lazy { QrCode.encode(ticket.statusUrl) }

    override fun onLayout(oldAttributes: PrintAttributes?, newAttributes: PrintAttributes, cancellationSignal: CancellationSignal, callback: LayoutResultCallback, extras: Bundle?) {
        if (cancellationSignal.isCanceled) { callback.onLayoutCancelled(); return }
        callback.onLayoutFinished(PrintDocumentInfo.Builder("intake-ticket-${ticket.jobNumber}.pdf").setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT).setPageCount(copies.size).build(), oldAttributes != newAttributes)
    }

    override fun onWrite(pages: Array<out PageRange>, destination: ParcelFileDescriptor, cancellationSignal: CancellationSignal, callback: WriteResultCallback) {
        val pdf = PdfDocument()
        try {
            copies.forEachIndexed { i, copy ->
                if (cancellationSignal.isCanceled) { callback.onWriteCancelled(); return }
                val page = pdf.startPage(PdfDocument.PageInfo.Builder(595, 842, i + 1).create())
                drawIntakeCopy(page.canvas, copy, qr)
                pdf.finishPage(page)
            }
            FileOutputStream(destination.fileDescriptor).use { pdf.writeTo(it) }
            callback.onWriteFinished(arrayOf(PageRange.ALL_PAGES))
        } catch (e: Exception) {
            callback.onWriteFailed(e.message)
        } finally { pdf.close() }
    }
}

internal fun drawIntakeCopy(canvas: Canvas, copy: IntakeTicketCopy, qr: Array<BooleanArray>) {
    val left = 40f; val right = 555f
    val ink = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.BLACK }
    val muted = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.DKGRAY; textSize = 11f }
    val title = Paint(ink).apply { textSize = 24f; typeface = Typeface.DEFAULT_BOLD }
    val label = Paint(ink).apply { textSize = 11f; typeface = Typeface.DEFAULT_BOLD }
    val value = Paint(ink).apply { textSize = 13f }
    val rule = Paint().apply { color = Color.LTGRAY; strokeWidth = 1f }
    var y = 70f
    canvas.drawText(copy.title, left, y, title); y += 20f
    canvas.drawText(copy.subtitle, left, y, muted); y += 16f
    canvas.drawLine(left, y, right, y, rule); y += 22f
    for ((k, v) in copy.rows) {
        canvas.drawText(k.uppercase(), left, y, label)
        val lines = wrapText(v, value, right - (left + 130f))
        lines.forEachIndexed { i, line -> canvas.drawText(line, left + 130f, y + i * 17f, value) }
        y += maxOf(1, lines.size) * 17f + 10f
        canvas.drawLine(left, y - 12f, right, y - 12f, rule)
    }
    y += 20f
    val cell = 4f; val quiet = 4
    val side = (qr.size + quiet * 2) * cell
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
            val candidate = if (line.isEmpty()) word else "$line $word"
            if (line.isNotEmpty() && paint.measureText(candidate) > width) { out.add(line); line = word } else line = candidate
        }
        out.add(line)
    }
    return out
}
