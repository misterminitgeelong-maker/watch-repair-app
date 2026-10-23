package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.niimbot.NiimbotDevice
import au.mainspring.nativeapp.niimbot.NiimbotKeyValueStore
import au.mainspring.nativeapp.niimbot.NiimbotLabelData
import au.mainspring.nativeapp.niimbot.NiimbotLastPrinter
import au.mainspring.nativeapp.niimbot.niimbotBalanceCents
import au.mainspring.nativeapp.niimbot.niimbotCopyTag
import au.mainspring.nativeapp.niimbot.niimbotDepBalText
import au.mainspring.nativeapp.niimbot.niimbotJobLabels
import au.mainspring.nativeapp.ui.IntakeTicketKind
import au.mainspring.nativeapp.ui.JobPrintContext
import au.mainspring.nativeapp.ui.printAfterIntakeBody
import au.mainspring.nativeapp.ui.printAfterIntakeTitle
import au.mainspring.nativeapp.ui.watchJobBundle
import org.junit.Assert.*
import org.junit.Test

class NiimbotLabelPairTest {
    private val base = NiimbotLabelData(jobNumber = "1042", customerName = "Sam", itemTitle = "Seiko 5", qrText = "https://x.test/status/t")

    @Test fun jobProducesWorkshopThenCustomerCopy() {
        val labels = niimbotJobLabels(base, "$20.00", "$80.00")
        assertEquals(2, labels.size)
        assertEquals("WORKSHOP COPY", niimbotCopyTag(labels[0]))
        assertEquals("CUSTOMER COPY", niimbotCopyTag(labels[1]))
        assertEquals("Dep: $20.00  Bal: $80.00", niimbotDepBalText(labels[0]))
        assertNull(niimbotDepBalText(labels[1]))
        assertEquals(labels[0].qrText, labels[1].qrText)
    }

    @Test fun depBalNeedsBothValues() {
        assertNull(niimbotDepBalText(base.copy(depositLabel = "$5.00")))
        assertNull(niimbotDepBalText(base.copy(balanceLabel = "$5.00", depositLabel = " ")))
    }

    @Test fun balanceUsesCostElsePreQuoteAndNeverGoesNegative() {
        assertEquals(8000, niimbotBalanceCents(10000, 5000, 2000))
        assertEquals(3000, niimbotBalanceCents(0, 5000, 2000))
        assertEquals(0, niimbotBalanceCents(1000, 0, 4000))
    }

    private class MemStore : NiimbotKeyValueStore {
        val map = HashMap<String, String>()
        override fun get(key: String) = map[key]
        override fun put(key: String, value: String?) { if (value == null) map.remove(key) else map[key] = value }
    }

    @Test fun lastPrinterIsRemembered() {
        val last = NiimbotLastPrinter(MemStore())
        assertNull(last.load())
        last.save(NiimbotDevice("M2-1234", "AA:BB:CC:DD:EE:FF"))
        assertEquals(NiimbotDevice("M2-1234", "AA:BB:CC:DD:EE:FF"), last.load())
        last.forget()
        assertNull(last.load())
    }

    @Test fun lastPrinterRejectsGarbageAddress() {
        val store = MemStore()
        val last = NiimbotLastPrinter(store)
        last.save(NiimbotDevice("x", "not-a-mac"))
        assertNull(last.load())
        store.put("last_address", "zz")
        assertNull(last.load())
    }

    private fun job(token: String? = "tok") = RepairJobRead(
        id = "j1", depositCents = 2000, preQuoteCents = 10000, costCents = 0, tenantId = "t", watchId = "w", jobNumber = "1042",
        title = "Service", description = null, status = "intake", priority = "normal", customerName = "Sam", createdAt = "2026-10-01",
        statusToken = token, watchBrand = "Seiko", watchModel = "5",
    )

    @Test fun watchBundleBuildsTicketAndTwoLabels() {
        val ctx = JobPrintContext("https://app.test/api", "Shop", "02", { "$%.2f".format(it / 100.0) }, { it })
        val bundle = watchJobBundle(job(), ctx)!!
        assertEquals("https://app.test/status/tok", bundle.ticket.statusUrl)
        assertEquals(2, bundle.labels.size)
        assertEquals("Dep: $20.00  Bal: $80.00", niimbotDepBalText(bundle.labels[0]))
        assertEquals("Seiko 5", bundle.labels[1].itemTitle)
        assertNull(watchJobBundle(job(token = null), ctx))
    }

    @Test fun promptWording() {
        assertEquals("Print labels?", printAfterIntakeTitle(1))
        assertEquals("Print labels for 3 jobs?", printAfterIntakeTitle(3))
        assertTrue(printAfterIntakeBody(2, IntakeTicketKind.WATCH).contains("2 repair jobs"))
    }
}
