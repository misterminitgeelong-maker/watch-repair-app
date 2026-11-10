package au.mainspring.nativeapp.ui

import android.content.Context
import android.graphics.pdf.PdfDocument
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.*

/** Reuses the app's QR renderer and Android print/PDF destination for event signs and tub tickets. */
fun printCommunityPages(context: Context, name: String, pages: List<Pair<IntakeTicketCopy, String>>) {
    require(pages.isNotEmpty())
    val sheets = pages.flatMap { (copy, url) -> paginateIntakeCopy(copy).map { it to url } }
    val manager = context.getSystemService(Context.PRINT_SERVICE) as? PrintManager ?: error("Printing is unavailable.")
    manager.print(name, object: PrintDocumentAdapter() {
        override fun onLayout(old: PrintAttributes?, attributes: PrintAttributes, cancellation: CancellationSignal, callback: LayoutResultCallback, extras: Bundle?) {
            if(cancellation.isCanceled) { callback.onLayoutCancelled(); return }
            callback.onLayoutFinished(PrintDocumentInfo.Builder("mainspring.pdf").setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT).setPageCount(sheets.size).build(), old != attributes)
        }
        override fun onWrite(ranges: Array<out PageRange>, destination: ParcelFileDescriptor, cancellation: CancellationSignal, callback: WriteResultCallback) {
            val pdf = PdfDocument()
            try {
                sheets.forEachIndexed { index, (copy, url) ->
                    if(cancellation.isCanceled) { callback.onWriteCancelled(); return }
                    if(ranges.any { index in it.start..it.end }) {
                        val page = pdf.startPage(PdfDocument.PageInfo.Builder(595, 842, index + 1).create())
                        drawIntakeCopy(page.canvas, copy, QrCode.encode(url)); pdf.finishPage(page)
                    }
                }
                java.io.FileOutputStream(destination.fileDescriptor).use { pdf.writeTo(it) }
                callback.onWriteFinished(ranges)
            } catch(e: Exception) { callback.onWriteFailed(e.message) } finally { pdf.close() }
        }
    }, PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).build())
}
