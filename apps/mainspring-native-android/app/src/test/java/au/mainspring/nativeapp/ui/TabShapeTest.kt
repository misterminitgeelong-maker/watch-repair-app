package au.mainspring.nativeapp.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class TabShapeTest {
    private fun keys(vararg f: String) = navTabs(f.toSet()).map { it.first }

    @Test fun threeServicesKeepWatchAndMobileOnly() =
        assertEquals(listOf("today", "inbox", "watch", "mobile", "more"), keys("watch", "shoe", "auto_key"))

    @Test fun twoServicesGetBothTabs() = assertEquals(listOf("today", "inbox", "watch", "shoe", "more"), keys("watch", "shoe"))

    @Test fun oneServiceIsNamedForItself() {
        assertEquals(listOf("today" to "Home", "inbox" to "Inbox", "mobile" to "Mobile", "more" to "More"), navTabs(setOf("auto_key")))
    }

    @Test fun noServiceHasNoServiceTab() = assertEquals(listOf("today", "inbox", "more"), keys())

    @Test fun routesMapToTheirTab() {
        val f = setOf("watch", "shoe", "auto_key")
        assertEquals("watch", tabFor("watch_jobs", f)); assertEquals("mobile", tabFor("auto_jobs", f))
        assertEquals("more", tabFor("shoe_jobs", f)); assertEquals("more", tabFor("jobs", f))
        assertEquals("today", tabFor("today", f)); assertEquals("inbox", tabFor("inbox", f)); assertEquals("more", tabFor("customers", f))
        assertEquals("shoe", tabFor("shoe_jobs", setOf("shoe")))
        assertEquals("watch_jobs", tabRoute("watch")); assertEquals("auto_jobs", tabRoute("mobile")); assertEquals("shoe_jobs", tabRoute("shoe"))
    }
}
