package au.mainspring.nativeapp.niimbot

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import au.mainspring.nativeapp.ui.QrCode

/** Fields for one intake label (port of JobLabelCore in niimbot.ts; deposit/balance omitted, not printed on the item). */
data class NiimbotLabelData(
    val jobNumber: String,
    val customerName: String?,
    val customerPhone: String? = null,
    val itemTitle: String,
    val services: String? = null,
    val dateIn: String? = null,
    /** Text encoded in the QR (the public status URL). */
    val qrText: String,
    val qrCaption: String = "Scan to track this repair",
    /** True for the CUSTOMER COPY: header tag changes, deposit/balance line is hidden. */
    val isCustomerCopy: Boolean = false,
    /** Pre-formatted money for the workshop line "Dep: x  Bal: y"; both must be set for it to print. */
    val depositLabel: String? = null,
    val balanceLabel: String? = null,
)

fun niimbotCopyTag(data: NiimbotLabelData): String = if (data.isCustomerCopy) "CUSTOMER COPY" else "WORKSHOP COPY"

/** "Dep: $20.00  Bal: $80.00" for the workshop copy only; null when not shown. */
fun niimbotDepBalText(data: NiimbotLabelData): String? {
    if (data.isCustomerCopy) return null
    val d = data.depositLabel?.takeIf { it.isNotBlank() } ?: return null
    val b = data.balanceLabel?.takeIf { it.isNotBlank() } ?: return null
    return "Dep: $d  Bal: $b"
}

/** Balance still owing, never negative (quote falls back to the pre-quote when no cost is set yet). */
fun niimbotBalanceCents(costCents: Int, preQuoteCents: Int, depositCents: Int): Int {
    val quote = if (costCents > 0) costCents else preQuoteCents
    return maxOf(quote - depositCents, 0)
}

/**
 * The two labels printed per job, in print order: WORKSHOP COPY (with deposit/balance) then CUSTOMER COPY.
 * [base] carries the shared fields; both copies encode the public status URL in [NiimbotLabelData.qrText].
 */
fun niimbotJobLabels(base: NiimbotLabelData, depositLabel: String?, balanceLabel: String?): List<NiimbotLabelData> = listOf(
    base.copy(isCustomerCopy = false, depositLabel = depositLabel, balanceLabel = balanceLabel, qrCaption = "Scan for repair status"),
    base.copy(isCustomerCopy = true, depositLabel = null, balanceLabel = null, qrCaption = "Scan to track this repair"),
)

fun niimbotTruncate(text: String, maxChars: Int): String = if (text.length <= maxChars) text else text.take(maxChars - 1) + "…"

/** Tall rolls (e.g. 50x70) stack text over a big QR; short ones (50x30) put the QR beside the text. */
fun niimbotIsTall(dots: LabelDots): Boolean = dots.height >= dots.width * 1.15

object NiimbotLabelRenderer {
    private const val PAD = 18f

    fun render(data: NiimbotLabelData, dots: LabelDots = NiimbotProtocol.DEFAULT_LABEL): Bitmap {
        val w = dots.width
        val h = dots.height
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        val s = w / 400f
        c.drawColor(Color.WHITE)
        val ink = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.BLACK }
        fun text(size: Float, bold: Boolean = false, mono: Boolean = false, color: Int = Color.BLACK) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            this.color = color; textSize = size * s
            typeface = Typeface.create(if (mono) Typeface.MONOSPACE else Typeface.SANS_SERIF, if (bold) Typeface.BOLD else Typeface.NORMAL)
        }

        // Border and header strip
        ink.style = Paint.Style.STROKE; ink.strokeWidth = 1f
        c.drawRect(0.5f, 0.5f, w - 0.5f, h - 0.5f, ink)
        ink.style = Paint.Style.FILL
        val headerH = 30 * s
        c.drawRect(0f, 0f, w.toFloat(), headerH, ink)
        c.drawText("MAINSPRING", PAD, 20 * s, text(14f, bold = true, color = Color.WHITE))
        val tag = text(11f, color = Color.WHITE)
        val tagText = niimbotCopyTag(data)
        c.drawText(tagText, w - PAD - tag.measureText(tagText), 20 * s, tag)

        val customer = data.customerName?.takeIf { it.isNotBlank() }
        if (niimbotIsTall(dots)) {
            var y = headerH + 48 * s
            c.drawText("#${data.jobNumber}", PAD, y, text(46f, bold = true, mono = true)); y += 32 * s
            if (customer != null) { c.drawText(niimbotTruncate(customer, 22), PAD, y, text(22f, bold = true)); y += 27 * s }
            val body = text(18f)
            data.customerPhone?.takeIf { it.isNotBlank() }?.let { c.drawText(it, PAD, y, body); y += 25 * s }
            c.drawText(niimbotTruncate(data.itemTitle, 26), PAD, y, body); y += 25 * s
            data.services?.takeIf { it.isNotBlank() }?.let { c.drawText(niimbotTruncate(it, 26), PAD, y, body); y += 25 * s }
            data.dateIn?.takeIf { it.isNotBlank() }?.let { c.drawText(it, PAD, y, body); y += 25 * s }
            niimbotDepBalText(data)?.let { c.drawText(it, PAD, y, text(16f)); y += 22 * s }
            val captionH = 18 * s
            val top = y + 10 * s
            val bottom = h - 10 * s - captionH
            val qrSize = maxOf(0f, minOf(w - 2 * PAD, bottom - top))
            if (qrSize > 24) {
                drawQr(c, data.qrText, (w - qrSize) / 2f, top, qrSize)
                val cap = text(12f, color = Color.parseColor("#444444"))
                c.drawText(data.qrCaption, (w - cap.measureText(data.qrCaption)) / 2f, top + qrSize + 14 * s, cap)
            }
        } else {
            val qrSize = minOf(120 * s, h - headerH - 10)
            drawQr(c, data.qrText, w - PAD - qrSize, headerH + 5, qrSize)
            c.drawText("#${data.jobNumber}", PAD, 74 * s, text(40f, bold = true, mono = true))
            var y = 102f
            if (customer != null) { c.drawText(niimbotTruncate(customer, 20), PAD, y * s, text(20f, bold = true)) } else y -= 23
            val body = text(17f)
            data.customerPhone?.takeIf { it.isNotBlank() }?.let { y += 23; c.drawText(it, PAD, y * s, body) }
            y += 23; c.drawText(niimbotTruncate(data.itemTitle, 24), PAD, y * s, body)
            data.services?.takeIf { it.isNotBlank() }?.let { y += 23; c.drawText(niimbotTruncate(it, 24), PAD, y * s, body) }
            data.dateIn?.takeIf { it.isNotBlank() }?.let { y += 23; c.drawText(it, PAD, y * s, body) }
            niimbotDepBalText(data)?.let { y += 21; c.drawText(it, PAD, y * s, text(15f)) }
            if (data.isCustomerCopy) c.drawText("Scan QR for live repair updates", PAD, h - 8f, text(11f, color = Color.parseColor("#444444")))
        }
        return bmp
    }

    private fun drawQr(c: Canvas, text: String, left: Float, top: Float, size: Float) {
        val modules = try { QrCode.encode(text) } catch (e: IllegalArgumentException) { return }
        val quiet = 2 // quiet-zone modules
        val total = modules.size + quiet * 2
        val cell = size / total
        val paint = Paint().apply { color = Color.BLACK; style = Paint.Style.FILL }
        for (r in modules.indices) for (col in modules[r].indices) if (modules[r][col]) {
            // snap to whole pixels so modules stay crisp after 1bpp thresholding
            val l = Math.round(left + (col + quiet) * cell).toFloat()
            val t = Math.round(top + (r + quiet) * cell).toFloat()
            c.drawRect(l, t, Math.round(left + (col + quiet + 1) * cell).toFloat(), Math.round(top + (r + quiet + 1) * cell).toFloat(), paint)
        }
    }

    /** Extract ARGB pixels for [NiimbotProtocol.rasterize]. */
    fun pixelsOf(bmp: Bitmap): IntArray = IntArray(bmp.width * bmp.height).also { bmp.getPixels(it, 0, bmp.width, 0, 0, bmp.width, bmp.height) }

    fun toRaster(data: NiimbotLabelData, dots: LabelDots = NiimbotProtocol.DEFAULT_LABEL): RasterPage {
        val bmp = render(data, dots)
        try { return NiimbotProtocol.rasterize(pixelsOf(bmp), bmp.width, bmp.height) } finally { bmp.recycle() }
    }
}
