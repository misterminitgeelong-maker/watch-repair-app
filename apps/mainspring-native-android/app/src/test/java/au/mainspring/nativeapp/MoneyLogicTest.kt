package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.InvoiceRead
import au.mainspring.nativeapp.api.InvoiceWithPayments
import au.mainspring.nativeapp.api.PaymentRead
import au.mainspring.nativeapp.ui.formatMoney
import au.mainspring.nativeapp.ui.lineTotalCents
import au.mainspring.nativeapp.ui.screens.revenueAmountLabel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class MoneyLogicTest {
    private fun inv(status: String, total: Int) = InvoiceRead("i", "t", "j", null, "INV-1", status, total, 0, total, "AUD", "2026-01-01T00:00:00Z")
    private fun pay(cents: Int) = PaymentRead("p", "i", cents, "AUD", "succeeded", "manual")
    private fun with(status: String, total: Int, vararg paid: Int) = InvoiceWithPayments(inv(status, total), paid.map { pay(it) })

    @Test fun partialPaymentsCountTowardPaid() {
        assertEquals(100_000 to 60_000, invoiceTotals(listOf(with("unpaid", 100_000, 60_000))))
    }

    @Test fun voidAndRefundedInvoicesAreExcluded() {
        assertEquals(50_000 to 0, invoiceTotals(listOf(with("void", 50_000), with("refunded", 20_000, 20_000), with("unpaid", 50_000))))
    }

    @Test fun paidInvoiceCountsInFullAndOverpaymentIsCapped() {
        assertEquals(30_000 to 30_000, invoiceTotals(listOf(with("paid", 10_000), with("unpaid", 20_000, 25_000))))
    }

    @Test fun lineTotalRoundsHalfUpAndKeepsFractions() {
        assertEquals(1000, lineTotalCents(2000, 0.5))
        assertEquals(3000, lineTotalCents(2000, 1.5))
        assertEquals(115, lineTotalCents(100, 1.15))
        assertEquals(2, lineTotalCents(1, 1.5))
    }

    @Test fun formatMoneyUsesSymbolThousandsAndOutsideSign() {
        assertEquals("$1,234.50", formatMoney(123_450, "AUD"))
        assertEquals("-$120.00", formatMoney(-12_000, "NZD"))
        assertEquals("$0.05", formatMoney(5, null))
        assertEquals("EUR 10.00", formatMoney(1000, "eur"))
    }

    @Test fun decimalCommaIsNotReadAsThousands() {
        assertEquals("1250.00", stripThousandsCommas("1,250.00"))
        assertEquals("12,50", stripThousandsCommas("12,50"))
        assertNull(InvoiceDetailViewModel.parseDollarsToCents("12,50"))
        assertEquals(125_000, InvoiceDetailViewModel.parseDollarsToCents("$1,250.00"))
        assertNull(parseInvoiceAmounts("10,00", "0", "10").first)
    }

    @Test fun unpricedRevenueIsNotShownAsZero() {
        val f = { c: Int -> "$$c" }
        assertEquals("3 unpriced", revenueAmountLabel(0, 3, f))
        assertEquals("$500 + 2 unpriced", revenueAmountLabel(500, 2, f))
        assertEquals("$0", revenueAmountLabel(0, 0, f))
    }
}
