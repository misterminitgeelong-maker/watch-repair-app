package au.mainspring.nativeapp

/** A shopfront on the booking-only plan has no repair, invoicing or inventory workspace. */
fun isBookingOnly(features: Set<String>): Boolean = "shop_mobile_booking" in features && features.none { it in setOf("watch", "shoe", "auto_key") }

/** Shared by the landing screen and app shell so unsupported workspaces never appear as dead links. */
fun bookingOnlyDestinations(owner: Boolean): List<Pair<String, String>> = buildList {
    add("bookingRequests" to "Booking requests")
    add("networkMessages" to "Messages")
    add("inbox" to "Inbox")
    if(owner) add("myShops" to "My Shops")
    add("accounts" to "Account")
}

fun bookingOnlyNavigation(): List<Pair<String, String>> = listOf("today" to "Home", "bookingRequests" to "Bookings", "networkMessages" to "Messages", "inbox" to "Inbox", "more" to "More")
