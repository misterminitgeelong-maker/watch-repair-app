package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier

/**
 * Pull-to-refresh around a list screen. [loading] is the view model's own flag; the pull spinner is only shown for a
 * user-initiated pull (the screen's own progress bar covers background loads), and clears when [loading] drops again.
 * Wrap the scrolling list; give the list `Modifier.fillMaxSize()` and pass any `weight`/size modifier here.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PullRefresh(loading: Boolean, onRefresh: () -> Unit, modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    var pulled by remember { mutableStateOf(false) }
    val refresh by rememberUpdatedState(onRefresh)
    LaunchedEffect(loading) { if (!loading) pulled = false }
    // Safety net: a refresh that never reports loading must not leave the spinner up.
    LaunchedEffect(pulled) { if (pulled) { kotlinx.coroutines.delay(15_000); pulled = false } }
    PullToRefreshBox(isRefreshing = pulled, onRefresh = { pulled = true; refresh() }, modifier = modifier, content = content)
}
