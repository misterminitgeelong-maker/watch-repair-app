package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ProspectLead
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ProspectLinksTest {
    private fun lead(id: String, visit: String?) = ProspectLead(id, id, null, null, null, "new", null, null, null, null, visit, null)

    @Test fun telUriKeepsPlusAndDigitsOnly() {
        assertEquals("tel:0412345678", prospectTelUri("0412 345 678"))
        assertEquals("tel:+61412345678", prospectTelUri(" +61 (412) 345-678 "))
        assertNull(prospectTelUri(""))
        assertNull(prospectTelUri(null))
        assertNull(prospectTelUri("n/a"))
    }

    @Test fun mapsUriEncodesNameAndAddress() {
        assertEquals("https://www.google.com/maps/search/?api=1&query=Key+%26+Lock+1+High+St", prospectMapsUri("Key & Lock", "1 High St"))
        assertEquals("https://www.google.com/maps/search/?api=1&query=Solo", prospectMapsUri("Solo", null))
    }

    @Test fun websiteGetsHttpsAndRejectsOtherSchemes() {
        assertEquals("https://example.com", prospectWebsiteUri("example.com"))
        assertEquals("http://example.com/a", prospectWebsiteUri("http://example.com/a"))
        assertNull(prospectWebsiteUri("javascript://alert(1)"))
        assertNull(prospectWebsiteUri("intent://x"))
        assertNull(prospectWebsiteUri("not a url"))
        assertNull(prospectWebsiteUri(null))
    }

    @Test fun visitsAreSoonestFirstAndSkipUnscheduled() {
        val rows = prospectVisits(listOf(lead("b", "2026-11-03T01:00:00Z"), lead("none", null), lead("a", "2026-11-01T01:00:00Z"), lead("blank", " ")))
        assertEquals(listOf("a", "b"), rows.map { it.id })
    }
}
