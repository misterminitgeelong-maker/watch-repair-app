package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.screens.customerTabs
import org.junit.Assert.assertEquals
import org.junit.Test

class CustomerTabsTest {
    @Test fun watchShopShowsJobsWatchesOrdersAccountWithCounts() {
        assertEquals(listOf("jobs" to "Jobs (5)", "watches" to "Watches (2)", "orders" to "Orders (1)", "account" to "Account"),
            customerTabs(setOf("watch", "shoe"), 5, 2, 1))
    }
    @Test fun nonWatchShopHidesWatchesAndUnloadedOrdersHaveNoCount() {
        assertEquals(listOf("jobs" to "Jobs (0)", "orders" to "Orders", "account" to "Account"), customerTabs(setOf("auto_key"), 0, 0, null))
    }
}
