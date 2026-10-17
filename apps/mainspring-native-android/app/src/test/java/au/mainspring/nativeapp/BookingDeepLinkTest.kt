package au.mainspring.nativeapp

import org.junit.After
import org.junit.Assert.*
import org.junit.Test

class BookingDeepLinkTest {
    private val id = "3f2b8c1e-5d4a-4e6b-9a7c-0123456789ab"
    @After fun reset() = DeepLinkInbox.clear()

    @Test fun parsesWebLink() = assertEquals(AcceptBookingLink(id), BookingDeepLink.parse("https://mainspring.au/auto-key?accept_booking=$id"))
    @Test fun parsesWwwHostAndTrailingSlashAndExtraParams() =
        assertEquals(AcceptBookingLink(id), BookingDeepLink.parse("https://WWW.Mainspring.au/auto-key/?utm=x&accept_booking=$id#top"))
    @Test fun parsesCustomSchemes() {
        assertEquals(AcceptBookingLink(id), BookingDeepLink.parse("mainspring://booking/accept?id=$id"))
        assertEquals(AcceptBookingLink(id), BookingDeepLink.parse("mainspring://auto-key?accept_booking=$id"))
    }
    @Test fun rejectsOtherHostsSchemesAndPaths() {
        assertNull(BookingDeepLink.parse("https://evil.example/auto-key?accept_booking=$id"))
        assertNull(BookingDeepLink.parse("http://mainspring.au/auto-key?accept_booking=$id"))
        assertNull(BookingDeepLink.parse("https://mainspring.au/jobs?accept_booking=$id"))
        assertNull(BookingDeepLink.parse("mainspring://booking/decline?id=$id"))
        assertNull(BookingDeepLink.parse("https://mainspring.au.evil.example/auto-key?accept_booking=$id"))
    }
    @Test fun rejectsMissingOrUnsafeIds() {
        assertNull(BookingDeepLink.parse("https://mainspring.au/auto-key"))
        assertNull(BookingDeepLink.parse("https://mainspring.au/auto-key?accept_booking="))
        assertNull(BookingDeepLink.parse("https://mainspring.au/auto-key?accept_booking=..%2F..%2Fadmin"))
        assertNull(BookingDeepLink.parse("https://mainspring.au/auto-key?accept_booking=a%20b"))
        assertNull(BookingDeepLink.parse("https://mainspring.au/auto-key?accept_booking=${"a".repeat(65)}"))
    }
    @Test fun rejectsGarbageAndNull() {
        assertNull(BookingDeepLink.parse(null)); assertNull(BookingDeepLink.parse("")); assertNull(BookingDeepLink.parse("not a uri %%"))
    }
    @Test fun customHostSetIsHonoured() =
        assertEquals(AcceptBookingLink("7"), BookingDeepLink.parse("https://staging.example/auto-key?accept_booking=7", setOf("staging.example")))
    @Test fun routeBuildsNavigationRoute() = assertEquals("acceptBooking/$id", BookingDeepLink.route(id))

    @Test fun inboxHoldsOnlyAcceptLinksAndConsumesOnce() {
        assertFalse(DeepLinkInbox.offer("https://mainspring.au/dashboard"))
        assertNull(DeepLinkInbox.pending.value)
        assertTrue(DeepLinkInbox.offer("https://mainspring.au/auto-key?accept_booking=$id"))
        val link = DeepLinkInbox.pending.value!!
        DeepLinkInbox.consume(AcceptBookingLink("other")); assertNotNull(DeepLinkInbox.pending.value)
        DeepLinkInbox.consume(link); assertNull(DeepLinkInbox.pending.value)
    }
}
