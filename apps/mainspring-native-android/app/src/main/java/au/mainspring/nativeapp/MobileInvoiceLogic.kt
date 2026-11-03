package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.MobileInvoiceAmounts
import au.mainspring.nativeapp.api.MobileInvoiceSend

/** Delivery channels for a mobile invoice (web `InvoiceSendChannel`). */
val INVOICE_CHANNELS = listOf("both" to "Text + Email", "sms" to "Text only", "email" to "Email only")

/** Plain-language result of a send, mirroring the web `invoiceSendFeedback`. */
fun invoiceSendFeedback(r: MobileInvoiceSend, channel: String): String {
    val parts = mutableListOf<String>()
    if(channel != "email") {
        if(r.smsSent) parts += "text sent"
        else if(r.smsReason == "no_phone") parts += "text skipped (no phone on file)"
        else if(!r.smsReason.isNullOrBlank() && r.smsReason != "not_requested") parts += "text not sent"
    }
    if(channel != "sms") {
        if(r.emailSent) parts += "email sent"
        else when(r.reason) {
            "no_email" -> parts += "email skipped (no email on file)"
            "email_disabled", "sendgrid_not_configured", "email_not_configured" -> parts += "email not configured on server"
            "send_failed" -> parts += r.emailError?.trim()?.takeIf { it.isNotEmpty() }?.let { "email failed: $it" } ?: "email failed"
        }
    }
    return if(parts.isEmpty()) "Invoice not sent: customer has no phone or email on file." else "Invoice ${parts.joinToString(", ")}."
}

/** Parses the three edit fields (dollars) into cents; returns null with a reason when invalid. */
fun parseInvoiceAmounts(subtotal: String, tax: String, total: String): Pair<MobileInvoiceAmounts?, String?> {
    fun cents(s: String): Int? {
        val t = s.trim().removePrefix("$").replace(",", "").trim()
        if(t.isEmpty()) return null
        return try { java.math.BigDecimal(t).movePointRight(2).setScale(0, java.math.RoundingMode.HALF_UP).intValueExact().takeIf { it >= 0 } } catch(_: Exception) { null }
    }
    val s = cents(subtotal); val x = cents(tax); val t = cents(total)
    if(s == null || x == null || t == null) return null to "Enter valid dollar amounts."
    if(t != s + x) return null to "Total must equal subtotal plus tax."
    return MobileInvoiceAmounts(s, x, t) to null
}
