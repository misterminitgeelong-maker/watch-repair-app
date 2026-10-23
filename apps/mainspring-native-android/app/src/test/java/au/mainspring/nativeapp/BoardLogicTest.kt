package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AccountInvoice
import au.mainspring.nativeapp.api.AccountStatementLine
import org.junit.Assert.assertEquals
import org.junit.Test

class BoardLogicTest {
    @Test fun addedLabelUsesShopTimezone() {
        assertEquals("Added 16/10/2026", customerAddedLabel("2026-10-15T20:00:00Z", "Australia/Melbourne"))
        assertEquals("Added 05/03/2026", customerAddedLabel("2026-03-05", "Australia/Melbourne"))
        assertEquals("", customerAddedLabel("garbage", "Australia/Melbourne"))
        assertEquals("", customerAddedLabel(null, "UTC"))
    }

    @Test fun csvQuotesAndExpandsLines() {
        val line = AccountStatementLine("watch", "j1", "W-1", "Strap, \"new\"", 1500)
        val csv = accountInvoicesCsv(listOf(
            AccountInvoice("a", "INV-1", 2026, 9, "sent", 1500, 150, 1650, "AUD", listOf(line), "2026-10-01T00:00:00Z"),
            AccountInvoice("b", "INV-2", 2026, 10, "draft", 0, 0, 0, "AUD"),
        ))
        val rows = csv.split("\n")
        assertEquals(3, rows.size)
        assertEquals("INV-1,2026,9,sent,1500,150,1650,watch,W-1,\"Strap, \"\"new\"\"\",1500,2026-10-01T00:00:00Z", rows[1])
        assertEquals("INV-2,2026,10,draft,0,0,0,,,,,", rows[2])
    }

    @Test fun csvFileName() {
        assertEquals("acme-pty-ltd-invoices.csv", accountInvoicesCsvFileName("Acme Pty. Ltd!"))
        assertEquals("customer-account-invoices.csv", accountInvoicesCsvFileName("!!!"))
    }

    @Test fun prospectNextStage() {
        assertEquals("contacted", prospectNextStage("new"))
        assertEquals("visited", prospectNextStage("contacted"))
        assertEquals("onboarded", prospectNextStage("visited"))
        assertEquals(null, prospectNextStage("onboarded"))
        assertEquals(null, prospectNextStage("lost"))
    }
}
