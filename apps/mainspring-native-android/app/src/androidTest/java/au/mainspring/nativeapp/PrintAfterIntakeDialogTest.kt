package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import au.mainspring.nativeapp.ui.IntakeTicketKind
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.PrintAfterIntakeDialog
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

/** The post-intake "Print labels?" prompt asks first and "Not now" dismisses it without touching the printer. */
class PrintAfterIntakeDialogTest {
    @get:Rule val compose = createComposeRule()

    @Test fun notNowDismissesWithoutPrinting() {
        var done = 0
        compose.setContent { MainspringTheme { PrintAfterIntakeDialog(IntakeTicketKind.WATCH, listOf("a", "b"), "https://x.test/api") { done++ } } }
        compose.onNodeWithText("Print labels for 2 jobs?").assertExists()
        compose.onNodeWithText("Not now").performClick()
        assertEquals(1, done)
    }
}
