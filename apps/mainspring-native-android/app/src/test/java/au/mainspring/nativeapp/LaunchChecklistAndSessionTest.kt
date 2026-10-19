package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.screens.checklistProgressLabel
import au.mainspring.nativeapp.ui.screens.launchChecklistItems
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LaunchChecklistAndSessionTest {
    @Test fun fourItemsWhenTeamCountUnknown() {
        val items = launchChecklistItems(1, 0, false, 0, null)
        assertEquals(4, items.size)
        assertEquals("Progress 1/4 completed", checklistProgressLabel(items))
    }

    @Test fun teamAccountsDoneOnlyWithMoreThanOneUser() {
        val solo = launchChecklistItems(1, 1, true, 1, 1)
        assertEquals(5, solo.size)
        assertFalse(solo.last().done)
        assertEquals("team", solo.last().route)
        assertEquals("Progress 4/5 completed", checklistProgressLabel(solo))
        val team = launchChecklistItems(1, 1, true, 1, 2)
        assertTrue(team.last().done)
        assertEquals("Progress 5/5 completed", checklistProgressLabel(team))
    }

    @Test fun sessionSummaryHidesSlugAndSpellsOutPlan() {
        val text = friendlySessionSummary("Native QA Owner", "owner", "Native QA Shop", "pro")
        assertEquals("Native QA Owner · Owner · Native QA Shop · Pro plan", text)
        assertFalse(text.contains("@"))
        assertEquals("Sam · Platform admin · Pro plan", friendlySessionSummary("Sam", "platform_admin", null, "pro"))
    }
}
