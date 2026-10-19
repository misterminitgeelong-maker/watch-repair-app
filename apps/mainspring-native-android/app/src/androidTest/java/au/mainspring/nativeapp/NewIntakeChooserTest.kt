package au.mainspring.nativeapp

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.NewIntakeScreen
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class NewIntakeChooserTest {
    @get:Rule val compose = createComposeRule()

    @Test fun onlyEnabledServicesAreShownAndContinueOpensTheChosenWizard() {
        var route: String? = null
        compose.setContent { MainspringTheme { NewIntakeScreen(setOf("watch", "shoe"), {}, { route = it }) } }
        compose.onNodeWithText("New Job Ticket").assertIsDisplayed()
        compose.onNodeWithTag("service-watch").assertIsDisplayed()
        compose.onNodeWithTag("service-shoe").assertIsDisplayed()
        compose.onNodeWithTag("service-auto_key").assertDoesNotExist()
        compose.onNodeWithTag("service-shoe").performClick()
        compose.onNodeWithTag("intake-continue").performClick()
        assertEquals("shoe_intake", route)
    }

    @Test fun defaultsToFirstEnabledServiceAndShowsDraftNote() {
        var route: String? = null
        compose.setContent { MainspringTheme { NewIntakeScreen(setOf("auto_key"), {}, { route = it }) } }
        compose.onNodeWithText("Draft saved on this device").assertIsDisplayed()
        compose.onNodeWithTag("intake-continue").performClick()
        assertEquals("mobile_intake", route)
    }
}
