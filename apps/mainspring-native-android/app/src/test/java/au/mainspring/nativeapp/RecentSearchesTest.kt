package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.SearchHit
import org.junit.Assert.assertEquals
import org.junit.Test

class RecentSearchesTest {
    private fun hit(id: String, kind: String = "customer") = SearchHit(kind = kind, id = id)

    @Test fun newestFirstAndDeduplicatedByKindAndId() {
        val list = pushRecent(pushRecent(pushRecent(emptyList(), hit("a")), hit("b")), hit("a"))
        assertEquals(listOf("a", "b"), list.map { it.id })
        assertEquals(2, pushRecent(list, hit("a", "invoice")).map { it.kind }.count { it == "customer" })
    }

    @Test fun listIsCapped() {
        var list = emptyList<SearchHit>()
        for (i in 1..12) list = pushRecent(list, hit("id$i"))
        assertEquals(RecentSearches.MAX, list.size)
        assertEquals("id12", list.first().id)
    }
}
