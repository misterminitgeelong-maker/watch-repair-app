package au.mainspring.nativeapp

import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.pdf.PdfRenderer
import android.os.ParcelFileDescriptor
import android.print.PageRange
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.CancellationException
import org.junit.*
import java.io.File

class InvoiceSummaryPrintTest {
    private fun summary(items: List<String> = listOf("Battery service\n1 × 100.00 AUD")) = InvoiceSummary("INV-TEST-01","unpaid",
        details = listOf("Customer: Avery Test","Created 07/10/2026"),items = items,
        totals = listOf("Subtotal" to "100.00 AUD","Tax / GST" to "10.00 AUD","Total" to "110.00 AUD","Paid" to "30.00 AUD","Remaining" to "80.00 AUD"))
    private fun <T> readPdf(bytes: ByteArray, block: (PdfRenderer) -> T): T {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File.createTempFile("invoice-summary-", ".pdf",context.cacheDir)
        try {
            file.writeBytes(bytes)
            return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY).use { descriptor -> PdfRenderer(descriptor).use(block) }
        } finally { file.delete() }
    }
    @Test fun invoiceSummaryRetainsServerTotalsAndRendersReadableA4Page() {
        val data = summary(); val layout = layoutInvoiceSummary(data)
        Assert.assertTrue(layout.pages.flatten().any { it.text == "Remaining: 80.00 AUD" })
        Assert.assertTrue(layout.pages.flatten().any { it.text == "Tax / GST: 10.00 AUD" })
        readPdf(renderInvoiceSummary(data,layout)) { renderer ->
            Assert.assertEquals(1,renderer.pageCount)
            renderer.openPage(0).use { page ->
                Assert.assertEquals(595,page.width); Assert.assertEquals(842,page.height)
                val image = Bitmap.createBitmap(page.width * 2,page.height * 2,Bitmap.Config.ARGB_8888).apply { eraseColor(Color.WHITE) }
                try {
                    page.render(image,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                    val context = InstrumentationRegistry.getInstrumentation().targetContext
                    val values = android.content.ContentValues().apply {
                        put(android.provider.MediaStore.Images.Media.DISPLAY_NAME,"invoice-summary-a4.png")
                        put(android.provider.MediaStore.Images.Media.MIME_TYPE,"image/png")
                        put(android.provider.MediaStore.Images.Media.RELATIVE_PATH,"Pictures/Mainspring-native-QA")
                        put(android.provider.MediaStore.Images.Media.IS_PENDING,1)
                    }
                    val uri = context.contentResolver.insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI,values)!!
                    context.contentResolver.openOutputStream(uri)!!.use { image.compress(Bitmap.CompressFormat.PNG,100,it) }
                    context.contentResolver.update(uri,android.content.ContentValues().apply { put(android.provider.MediaStore.Images.Media.IS_PENDING,0) },null,null)
                } finally { image.recycle() }
            }
        }
    }
    @Test fun longDescriptionsPaginateAndSelectedPageRangeProducesOnlyRequestedPage() {
        val data = summary(List(40) { index -> "Repair ${index + 1}: " + "Long service description with quantities and prices. ".repeat(8) })
        val layout = layoutInvoiceSummary(data)
        Assert.assertTrue(layout.pages.size > 1)
        readPdf(renderInvoiceSummary(data,layout)) { Assert.assertEquals(layout.pages.size,it.pageCount) }
        readPdf(renderInvoiceSummary(data,layout,arrayOf(PageRange(1,1)))) { Assert.assertEquals(1,it.pageCount) }
    }
    @Test fun cancellationDuringDrawingFinishesOpenPageAndKeepsCancellationOutcome() {
        var checks = 0
        try { renderInvoiceSummary(summary(),cancelled = { ++checks > 5 }); Assert.fail("Cancelled document was written") }
        catch(_: CancellationException) { }
    }
}
