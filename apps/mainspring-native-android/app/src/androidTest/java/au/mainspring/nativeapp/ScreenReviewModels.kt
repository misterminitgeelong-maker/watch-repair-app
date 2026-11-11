package au.mainspring.nativeapp

import androidx.compose.runtime.Composable
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import au.mainspring.nativeapp.api.SessionResponse

/** Capture-only types. The release app has no screenshot navigation or fixture hooks. */
data class ReviewData(val session: SessionResponse, val ids: Map<String, String>) {
    fun id(key: String): String = requireNotNull(ids[key]) { "Missing screenshot fixture: $key" }
    val baseUrl: String = "http://127.0.0.1:8716/"
}

data class ReviewCase(
    val id: String,
    val title: String,
    val group: String,
    val content: @Composable () -> Unit,
    val prepare: (ComposeContentTestRule) -> Unit = {},
    val note: String = "Sample data · native Android",
)
