package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.SubscriptionNotice
import au.mainspring.nativeapp.ui.subscriptionNotice
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

class ServerTimeTest {
    private val melbourne = ZoneId.of("Australia/Melbourne")
    private val utc = Instant.parse("2026-11-01T03:00:00Z")

    @Test fun parsesEveryServerShape() {
        assertEquals(utc, parseServerInstant("2026-11-01T03:00:00Z"))
        assertEquals(utc, parseServerInstant("2026-11-01T03:00:00+00:00"))
        assertEquals(utc, parseServerInstant("2026-11-01T14:00:00+11:00"))
        assertEquals(utc, parseServerInstant("2026-11-01T03:00:00"))
        assertEquals(utc.plusNanos(123_456_000), parseServerInstant("2026-11-01T03:00:00.123456"))
        assertEquals(Instant.parse("2026-11-01T00:00:00Z"), parseServerInstant("2026-11-01"))
    }

    @Test fun neverThrowsAndReturnsNullWhenUnreadable() {
        assertNull(parseServerInstant(null)); assertNull(parseServerInstant("")); assertNull(parseServerInstant("   "))
        assertNull(parseServerInstant("not a date")); assertNull(parseServerInstant("2026-13-45"))
    }

    @Test fun shopTodayUsesTheGivenZone() {
        val kiritimati = ZoneId.of("Pacific/Kiritimati"); val pago = ZoneId.of("Pacific/Pago_Pago")
        assertEquals(LocalDate.now(kiritimati), shopToday(kiritimati))
        assertEquals(LocalDate.now(pago), shopToday(pago))
    }

    @Test fun serverShopDateConvertsInstantsButKeepsPlainDates() {
        // 08:00 Melbourne on 24 Nov is 21:00 UTC on 23 Nov.
        assertEquals(LocalDate.parse("2026-11-24"), serverShopDate("2026-11-23T21:00:00Z", melbourne))
        assertEquals(LocalDate.parse("2026-11-24"), serverShopDate("2026-11-23T22:00:00", melbourne))
        assertEquals(LocalDate.parse("2026-11-24"), serverShopDate("2026-11-24", melbourne))
        assertNull(serverShopDate(null, melbourne)); assertNull(serverShopDate("junk", melbourne))
    }

    @Test fun daysInShopToleratesNaiveAndBlank() {
        val now = Instant.parse("2026-11-23T00:00:00Z")
        assertEquals(10, daysInShop("2026-11-13T00:00:00", now))
        assertEquals(10, daysInShop("2026-11-13T00:00:00Z", now))
        assertEquals(0, daysInShop("", now)); assertEquals(0, daysInShop("junk", now))
    }

    @Test fun trialBannerReadsNaiveTrialEnd() {
        val now = Instant.parse("2026-11-23T00:00:00Z")
        assertEquals(SubscriptionNotice.TrialEnding(7), subscriptionNotice("trialing", "2026-11-30T00:00:00", "owner", now))
        assertEquals(SubscriptionNotice.TrialEnding(7), subscriptionNotice("trialing", "2026-11-30T00:00:00+00:00", "owner", now))
        assertNull(subscriptionNotice("trialing", "2026-11-20T00:00:00", "owner", now))
        assertNull(subscriptionNotice("trialing", "garbage", "owner", now))
    }

    @Test fun pastCollectionUsesInjectedToday() {
        val today = LocalDate.parse("2026-11-24")
        assertFalse(isPastCollection("2026-11-24", today)); assertTrue(isPastCollection("2026-11-23", today))
    }
}
