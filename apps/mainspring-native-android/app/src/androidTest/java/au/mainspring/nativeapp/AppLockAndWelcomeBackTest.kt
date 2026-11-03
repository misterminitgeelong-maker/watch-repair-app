package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.AppLockOverlay
import au.mainspring.nativeapp.ui.screens.LoginScreen
import org.junit.Assert
import org.junit.Before
import org.junit.Rule
import org.junit.Test

class AppLockAndWelcomeBackTest {
    @get:Rule val compose = createComposeRule()
    @Before fun setup() {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        TokenStore.init(ctx); TokenStore.clear()
        ctx.getSharedPreferences("mainspring_login_prefs", 0).edit().clear().commit()
    }

    @Test fun welcomeBackPromptFillsInShopAndEmail() {
        LoginPrefs.save("native-qa", true); LoginPrefs.saveEmail("sam@example.test")
        compose.setContent { MainspringTheme { LoginScreen(AuthUiState(sessionEnded = true), "https://example.test/", { _, _, _, _ -> }) } }
        compose.onNodeWithTag("welcome-back").assertExists()
        compose.onNodeWithText("native-qa").assertExists()
        compose.onNodeWithText("sam@example.test").assertExists()
    }

    @Test fun normalSignInIsUnchangedAndDoesNotPrefillEmail() {
        LoginPrefs.save("native-qa", true); LoginPrefs.saveEmail("sam@example.test")
        compose.setContent { MainspringTheme { LoginScreen(AuthUiState(), "https://example.test/", { _, _, _, _ -> }) } }
        compose.onNodeWithTag("welcome-back").assertDoesNotExist()
        compose.onNodeWithText("sam@example.test").assertDoesNotExist()
    }

    @Test fun lockOverlayCoversTheAppAndOffersSignOutWithoutAPassword() {
        var signedOut = false
        compose.setContent { MainspringTheme { AppLockOverlay({}, { signedOut = true }) } }
        compose.onNodeWithTag("app-lock").assertExists()
        compose.onNodeWithText("Mainspring is locked").assertExists()
        compose.onAllNodesWithText("Password").assertCountEquals(0)
        compose.onNodeWithText("Sign out").performClick()
        Assert.assertTrue(signedOut)
    }

    @Test fun lockSettingPersistsAndColdStartLocksOnlyWhenOn() {
        AppLock.setEnabled(false); AppLock.onColdStart(); Assert.assertFalse(AppLock.locked.value)
        AppLock.setEnabled(true); AppLock.onColdStart(); Assert.assertTrue(AppLock.locked.value)
        AppLock.unlocked(); Assert.assertFalse(AppLock.locked.value)
        AppLock.setEnabled(false)
    }
}
