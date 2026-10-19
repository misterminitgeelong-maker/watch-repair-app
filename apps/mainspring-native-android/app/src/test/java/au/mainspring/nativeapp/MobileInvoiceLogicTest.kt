package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.MobileInvoice
import au.mainspring.nativeapp.api.MobileInvoiceSend
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class MobileInvoiceLogicTest {
    private val inv = MobileInvoice("i", "INV-1", "unpaid", "q", 1000, "AUD")
    private fun send(email: Boolean = false, sms: Boolean = false, emailReason: String? = null, smsReason: String? = null, err: String? = null) =
        MobileInvoiceSend(inv, email, sms, emailReason, smsReason, err)

    @Test fun feedbackReportsBothChannels() {
        assertEquals("Invoice text sent, email sent.", invoiceSendFeedback(send(email = true, sms = true), "both"))
    }

    @Test fun feedbackOnlyMentionsRequestedChannel() {
        assertEquals("Invoice text sent.", invoiceSendFeedback(send(email = false, sms = true, emailReason = "not_requested"), "sms"))
        assertEquals("Invoice email sent.", invoiceSendFeedback(send(email = true), "email"))
    }

    @Test fun feedbackExplainsSkips() {
        assertEquals("Invoice text skipped (no phone on file), email skipped (no email on file).",
            invoiceSendFeedback(send(emailReason = "no_email", smsReason = "no_phone"), "both"))
        assertEquals("Invoice email failed: boom.", invoiceSendFeedback(send(emailReason = "send_failed", err = "boom"), "email"))
        assertEquals("Invoice email not configured on server.", invoiceSendFeedback(send(emailReason = "email_disabled"), "email"))
        assertEquals("Invoice not sent: customer has no phone or email on file.", invoiceSendFeedback(send(), "both"))
    }

    @Test fun amountsParseToCentsAndMustAddUp() {
        val ok = parseInvoiceAmounts("90.91", "9.09", "100.00")
        assertNull(ok.second)
        assertEquals(10000, ok.first!!.total)
        assertEquals(9091, ok.first!!.subtotal)
        assertEquals(909, ok.first!!.tax)
        assertNotNull(parseInvoiceAmounts("$1,000.00", "0", "1000").first)
    }

    @Test fun badAmountsAreRejected() {
        assertNull(parseInvoiceAmounts("", "0", "0").first)
        assertNull(parseInvoiceAmounts("abc", "0", "0").first)
        assertNull(parseInvoiceAmounts("-5", "0", "-5").first)
        assertEquals("Total must equal subtotal plus tax.", parseInvoiceAmounts("10", "1", "12").second)
    }
}
