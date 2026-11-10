package au.mainspring.nativeapp

import org.junit.Assert.*
import org.junit.Test

class BookingOnlyPolicyTest {
    @Test fun bookingPlanGetsDedicatedHomeButMixedServicesKeepTheirWorkspace() {
        assertTrue(isBookingOnly(setOf("shop_mobile_booking")))
        assertTrue(isBookingOnly(setOf("shop_mobile_booking", "multi_site")))
        listOf("watch", "shoe", "auto_key").forEach { assertFalse(isBookingOnly(setOf("shop_mobile_booking", it))) }
        assertFalse(isBookingOnly(emptySet()))
    }
    @Test fun navigationAlwaysKeepsBookingsMessagesAndInboxWithoutUnsupportedTools() {
        val routes = bookingOnlyNavigation().map { it.first }
        assertTrue(routes.containsAll(listOf("bookingRequests", "networkMessages", "inbox")))
        assertEquals(5, routes.size)
        assertFalse(routes.any { it in listOf("jobs", "invoices", "stock", "watch_jobs", "shoe_jobs", "auto_jobs") })
    }
    @Test fun onlyShopOwnerGetsNetworkMembershipManagement() {
        assertTrue(bookingOnlyDestinations(true).any { it.first == "myShops" })
        assertFalse(bookingOnlyDestinations(false).any { it.first == "myShops" })
        assertTrue(bookingOnlyDestinations(false).map { it.first }.containsAll(listOf("bookingRequests", "networkMessages", "inbox", "accounts")))
    }
}
