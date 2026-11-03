package au.mainspring.nativeapp

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class JobWorkflowTest {
    @Test fun watchSuggestionsFollowWebStatusFlow() {
        assertEquals(listOf("awaiting_go_ahead"), suggestedWatchStatuses("awaiting_quote"))
        assertEquals(listOf("go_ahead", "no_go"), suggestedWatchStatuses("awaiting_go_ahead"))
        assertEquals(listOf("completed", "awaiting_parts"), suggestedWatchStatuses("working_on"))
        assertEquals(emptyList<String>(), suggestedWatchStatuses("collected"))
        assertEquals(emptyList<String>(), suggestedWatchStatuses("no_go"))
    }

    @Test fun shoeSuggestions() {
        assertEquals(listOf("working_on"), suggestedShoeStatuses("go_ahead"))
        assertEquals(listOf("collected"), suggestedShoeStatuses("awaiting_collection"))
        assertEquals(emptyList<String>(), suggestedShoeStatuses("collected"))
    }

    @Test fun stepIndexGroupsStatuses() {
        assertEquals(2, workflowStepIndex(WATCH_WORKFLOW_STEPS, "awaiting_parts"))
        assertEquals(2, workflowStepIndex(SHOE_WORKFLOW_STEPS, "working_on"))
        assertEquals(0, workflowStepIndex(WATCH_WORKFLOW_STEPS, "no_go"))
    }

    @Test fun daysInShopBands() {
        assertEquals(0, daysInShopSeverity(6)); assertEquals(1, daysInShopSeverity(7)); assertEquals(2, daysInShopSeverity(14))
        assertEquals("1 day in shop", daysInShopText(1)); assertEquals("3 days in shop", daysInShopText(3))
    }

    @Test fun navNeighbours() {
        JobNavContext.set("watch", listOf("a", "b", "c"))
        assertEquals(null to "b", JobNavContext.neighbors("watch", "a"))
        assertEquals("a" to "c", JobNavContext.neighbors("watch", "b"))
        assertEquals("b" to null, JobNavContext.neighbors("watch", "c"))
        assertEquals(2 to 3, JobNavContext.position("watch", "b"))
        assertEquals(null to null, JobNavContext.neighbors("watch", "zzz"))
        assertEquals(null to null, JobNavContext.neighbors("shoe", "a"))
        JobNavContext.clear()
    }

    private class Mem : ViewStorage {
        val m = HashMap<String, String>()
        override fun read(key: String) = m[key]
        override fun write(key: String, value: String) { m[key] = value }
    }

    @Test fun savedViewsRoundTripAndScope() {
        val mem = Mem(); var scope: String? = "t1|u1"
        val store = SavedViewsStore(mem) { scope }
        store.save("watch", SavedJobView("Mine old", statusFilter = "working_on", minDaysInShop = 14, technicianId = "u1", board = true))
        store.save("watch", SavedJobView("  Mine OLD ", statusFilter = "completed"))
        assertEquals(1, store.load("watch").size)
        assertEquals("completed", store.load("watch")[0].statusFilter)
        assertEquals("Mine OLD", store.load("watch")[0].name)
        assertEquals(emptyList<SavedJobView>(), store.load("shoe"))
        scope = "t1|u2"
        assertEquals(emptyList<SavedJobView>(), store.load("watch"))
        scope = "t1|u1"
        assertEquals(emptyList<SavedJobView>(), store.delete("watch", "mine old"))
        scope = null
        store.save("watch", SavedJobView("x")); assertEquals(emptyList<SavedJobView>(), store.load("watch"))
    }

    @Test fun savedViewsToleratesCorruptAndBlank() {
        val mem = Mem(); val store = SavedViewsStore(mem) { "s" }
        mem.m["saved_views:s:watch"] = "not json"
        assertEquals(emptyList<SavedJobView>(), store.load("watch"))
        assertEquals(0, store.save("watch", SavedJobView("   ")).size)
        for (i in 1..20) store.save("watch", SavedJobView("v$i"))
        assertEquals(SavedViewsStore.MAX_VIEWS, store.load("watch").size)
        assertNull(store.load("watch").firstOrNull { it.name == "v1" })
    }
}
