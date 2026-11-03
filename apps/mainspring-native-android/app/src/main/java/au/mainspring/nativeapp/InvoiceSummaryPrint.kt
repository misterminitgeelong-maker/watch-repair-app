package au.mainspring.nativeapp

import android.content.Context
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.*
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import kotlinx.coroutines.*
import java.io.ByteArrayOutputStream
import java.io.FileOutputStream
import kotlin.math.roundToInt

/** Read-only summary of the loaded server document; it does not invent merchant or tax details. */
data class InvoiceSummary(val number: String, val status: String, val details: List<String> = emptyList(),
    val items: List<String> = emptyList(), val totals: List<Pair<String,String>>)
internal data class SummaryPaper(val width: Int = 595, val height: Int = 842, val left: Float = 36f,
    val right: Float = 36f, val top: Float = 36f, val bottom: Float = 36f)
internal data class SummaryText(val text: String, val size: Float = 11f, val bold: Boolean = false, val after: Float = 4f)
internal data class SummaryLine(val text: String, val size: Float, val bold: Boolean, val height: Float)
internal data class SummaryLayout(val paper: SummaryPaper, val pages: List<List<SummaryLine>>)

internal fun layoutInvoiceSummary(summary: InvoiceSummary, paper: SummaryPaper = SummaryPaper(), cancelled: () -> Boolean = { false }): SummaryLayout {
    val width = (paper.width - paper.left - paper.right).toInt()
    val available = paper.height - paper.top - paper.bottom - 58f
    require(width >= 100 && available >= 100) { "Choose a larger paper size for this invoice summary." }
    val rows = buildList {
        add(SummaryText("Invoice summary",20f,true,10f))
        add(SummaryText("#${summary.number}",14f,true))
        add(SummaryText("Status: ${summary.status.replace('_',' ')}",12f,false,10f))
        summary.details.filter(String::isNotBlank).forEach { add(SummaryText(it)) }
        if(summary.items.isNotEmpty()) {
            add(SummaryText("Items",14f,true,8f))
            summary.items.forEach { add(SummaryText(it,after = 8f)) }
        }
        add(SummaryText("Totals",14f,true,8f))
        summary.totals.forEach { (label,value) -> add(SummaryText("$label: $value",12f,label == "Total" || label == "Remaining",6f)) }
    }
    val pages = mutableListOf<List<SummaryLine>>()
    var current = mutableListOf<SummaryLine>()
    var used = 0f
    rows.forEach { row ->
        if(cancelled()) throw CancellationException("Printing cancelled")
        val paint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply { textSize = row.size; typeface = Typeface.create("sans-serif",if(row.bold) Typeface.BOLD else Typeface.NORMAL) }
        val layout = StaticLayout.Builder.obtain(row.text,0,row.text.length,paint,width).setAlignment(Layout.Alignment.ALIGN_NORMAL).setIncludePad(false).build()
        for(index in 0 until layout.lineCount) {
            val text = row.text.substring(layout.getLineStart(index),layout.getLineEnd(index)).trimEnd('\n','\r')
            val height = paint.fontMetrics.descent - paint.fontMetrics.ascent + 3f + if(index == layout.lineCount - 1) row.after else 0f
            if(current.isNotEmpty() && used + height > available) { pages.add(current); current = mutableListOf(); used = 0f }
            current.add(SummaryLine(text,row.size,row.bold,height)); used += height
        }
    }
    if(current.isNotEmpty()) pages.add(current)
    return SummaryLayout(paper,pages)
}

internal fun renderInvoiceSummary(summary: InvoiceSummary, layout: SummaryLayout = layoutInvoiceSummary(summary), ranges: Array<PageRange> = arrayOf(PageRange.ALL_PAGES), cancelled: () -> Boolean = { false }): ByteArray {
    val pdf = PdfDocument()
    val paper = layout.paper
    try {
        val selected = layout.pages.indices.filter { index -> ranges.any { index in it.start..it.end } }
        require(selected.isNotEmpty()) { "No printable pages were selected." }
        selected.forEach { index ->
            if(cancelled()) throw CancellationException("Printing cancelled")
            val page = pdf.startPage(PdfDocument.PageInfo.Builder(paper.width,paper.height,index + 1).create())
            try {
            val canvas = page.canvas
            canvas.drawColor(Color.WHITE)
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.DKGRAY; textSize = 9f; typeface = Typeface.create("sans-serif",Typeface.NORMAL) }
            canvas.drawText("Mainspring",paper.left,paper.top + 10f,paint)
            paint.textAlign = Paint.Align.RIGHT
            canvas.drawText("#${summary.number}",paper.width - paper.right,paper.top + 10f,paint)
            paint.textAlign = Paint.Align.LEFT
            var y = paper.top + 34f
            layout.pages[index].forEach { line ->
                if(cancelled()) throw CancellationException("Printing cancelled")
                paint.color = Color.BLACK; paint.textSize = line.size; paint.typeface = Typeface.create("sans-serif",if(line.bold) Typeface.BOLD else Typeface.NORMAL)
                canvas.drawText(line.text,paper.left,y - paint.fontMetrics.ascent,paint)
                y += line.height
            }
            paint.color = Color.DKGRAY; paint.textSize = 9f; paint.typeface = Typeface.create("sans-serif",Typeface.NORMAL)
            canvas.drawText("Page ${index + 1} of ${layout.pages.size}",paper.left,paper.height - paper.bottom - 5f,paint)
            } finally { pdf.finishPage(page) }
        }
        return ByteArrayOutputStream().use { pdf.writeTo(it); it.toByteArray() }
    } finally { pdf.close() }
}

fun printInvoiceSummary(context: Context, summary: InvoiceSummary) {
    val manager = context.getSystemService(Context.PRINT_SERVICE) as? PrintManager ?: error("Printing is unavailable on this device.")
    manager.print("Invoice ${summary.number}",InvoiceSummaryAdapter(summary),PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).build())
}

private class InvoiceSummaryAdapter(private val summary: InvoiceSummary) : PrintDocumentAdapter() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var layout: SummaryLayout? = null
    private var layoutJob: Job? = null
    override fun onLayout(oldAttributes: PrintAttributes?, newAttributes: PrintAttributes, cancellationSignal: CancellationSignal, callback: LayoutResultCallback, extras: Bundle?) {
        layoutJob?.cancel()
        layout = null
        val request = scope.launch {
            try {
                val media = newAttributes.mediaSize ?: PrintAttributes.MediaSize.ISO_A4
                val margins = newAttributes.minMargins ?: PrintAttributes.Margins(500,500,500,500)
                fun points(mils: Int) = mils * 72f / 1000f
                val paper = SummaryPaper(points(media.widthMils).roundToInt(),points(media.heightMils).roundToInt(),
                    points(margins.leftMils).coerceAtLeast(24f),points(margins.rightMils).coerceAtLeast(24f),
                    points(margins.topMils).coerceAtLeast(24f),points(margins.bottomMils).coerceAtLeast(24f))
                val result = withContext(Dispatchers.IO) { layoutInvoiceSummary(summary,paper) { cancellationSignal.isCanceled || !isActive } }
                layout = result
                callback.onLayoutFinished(PrintDocumentInfo.Builder("invoice-summary.pdf").setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT).setPageCount(result.pages.size).build(),oldAttributes != newAttributes)
            } catch(_: CancellationException) { callback.onLayoutCancelled() }
            catch(e: Exception) { callback.onLayoutFailed(e.message ?: "Could not prepare the invoice summary.") }
        }
        layoutJob = request
        cancellationSignal.setOnCancelListener { request.cancel() }
    }
    override fun onWrite(pages: Array<PageRange>, destination: ParcelFileDescriptor, cancellationSignal: CancellationSignal, callback: WriteResultCallback) {
        val planned = layout ?: run { callback.onWriteFailed("Prepare the document before printing."); return }
        val job = scope.launch {
            try {
                withContext(Dispatchers.IO) {
                    val bytes = renderInvoiceSummary(summary,planned,pages) { cancellationSignal.isCanceled || !isActive }
                    ensureActive()
                    if(cancellationSignal.isCanceled) throw CancellationException("Printing cancelled")
                    FileOutputStream(destination.fileDescriptor).use { it.write(bytes) }
                }
                callback.onWriteFinished(pages)
            } catch(_: CancellationException) { callback.onWriteCancelled() }
            catch(e: Exception) { callback.onWriteFailed(e.message ?: "Could not write the invoice summary.") }
        }
        cancellationSignal.setOnCancelListener { job.cancel() }
    }
    override fun onFinish() { scope.cancel() }
}
