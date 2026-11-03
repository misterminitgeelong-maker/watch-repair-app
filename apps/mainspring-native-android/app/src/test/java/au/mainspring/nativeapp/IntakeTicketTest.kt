package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.IntakeTicket
import au.mainspring.nativeapp.ui.IntakeTicketKind
import au.mainspring.nativeapp.ui.QrCode
import au.mainspring.nativeapp.ui.intakeStatusUrl
import au.mainspring.nativeapp.ui.intakeTicketCopies
import org.junit.Assert.*
import org.junit.Test

class IntakeTicketTest {
    private fun ticket(kind: IntakeTicketKind = IntakeTicketKind.WATCH) = IntakeTicket("W-12", "Sam", "0400", "Seiko 5", "Service", null, "50.00 AUD", "https://x.test/status/abc", "Shop", "02", kind)

    @Test fun statusUrlUsesOriginAndKindPath() {
        assertEquals("https://app.test/status/tok", intakeStatusUrl("https://app.test/api/v1/", IntakeTicketKind.WATCH, "tok"))
        assertEquals("http://10.0.2.2:8000/shoe-status/tok", intakeStatusUrl("http://10.0.2.2:8000/api", IntakeTicketKind.SHOE, "tok"))
    }

    @Test fun copiesCarryTicketDetails() {
        val (workshop, customer) = intakeTicketCopies(ticket())
        assertTrue(workshop.rows.contains("Ticket #" to "W-12"))
        assertTrue(workshop.rows.contains("Due" to "—"))
        assertTrue(customer.rows.contains("Due" to "TBC"))
        assertTrue(customer.rows.contains("Deposit paid" to "50.00 AUD"))
    }

    @Test fun qrMatrixHasFinderPatternsAndGrowsWithText() {
        val small = QrCode.encode("hi")
        assertEquals(21, small.size)
        for ((r, c) in listOf(0 to 0, 0 to 14, 14 to 0)) {
            assertTrue(small[r][c]); assertTrue(small[r + 6][c + 6]); assertFalse(small[r + 1][c + 1]); assertTrue(small[r + 3][c + 3])
        }
        val url = QrCode.encode("https://app.mainspring.example/shoe-status/0123456789abcdef0123456789abcdef")
        assertTrue(url.size > 21)
        assertEquals(0, (url.size - 17) % 4)
        assertTrue(url.all { it.size == url.size })
    }

    @Test fun qrIsDeterministicAndRejectsOversizedText() {
        assertTrue(QrCode.encode("abc").contentDeepEquals(QrCode.encode("abc")))
        assertThrows(IllegalArgumentException::class.java) { QrCode.encode("x".repeat(400)) }
    }
}
