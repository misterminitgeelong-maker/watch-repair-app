package au.mainspring.nativeapp

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.SavedViewsRow
import org.junit.Assert
import org.junit.Rule
import org.junit.Test

/** Saved views control on the Shoe and Watch lists: save the current filters under a name, apply a view, delete it. */
class SavedViewsRowTest {
    @get:Rule val compose = createComposeRule()

    private fun content(views: MutableList<SavedJobView>, applied: MutableList<SavedJobView>, current: SavedJobView) {
        compose.setContent {
            var list by mutableStateOf(views.toList())
            MainspringTheme {
                SavedViewsRow(list, { current }, { applied.add(it) },
                    { v -> views.removeAll { it.name == v.name }; views.add(v); list = views.toList() },
                    { n -> views.removeAll { it.name == n }; list = views.toList() })
            }
        }
    }

    @Test fun savesTheCurrentFiltersUnderANameThenAppliesAndDeletesIt() {
        val views = mutableListOf<SavedJobView>()
        val applied = mutableListOf<SavedJobView>()
        content(views, applied, SavedJobView("", statusFilter = "working_on", showCompleted = true, query = "heel", minDaysInShop = 7, costOutliers = true))
        compose.onNodeWithTag("saved-view-manage").assertDoesNotExist()
        compose.onNodeWithTag("saved-view-save").performClick()
        compose.onNodeWithText("Save").assertIsNotEnabled()
        compose.onNodeWithText("View name").performTextInput("Heels overdue")
        compose.onNodeWithText("Save").performClick()
        Assert.assertEquals(listOf("Heels overdue"), views.map { it.name })
        Assert.assertEquals("working_on", views[0].statusFilter)
        Assert.assertTrue(views[0].costOutliers)
        compose.onNodeWithTag("saved-view-Heels overdue").performClick()
        Assert.assertEquals("heel", applied.single().query)
        compose.onNodeWithTag("saved-view-manage").performClick()
        compose.onNodeWithContentDescription("Delete saved view Heels overdue").performClick()
        Assert.assertTrue(views.isEmpty())
        compose.onNodeWithTag("saved-view-Heels overdue").assertDoesNotExist()
    }
}
