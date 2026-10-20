package au.mainspring.nativeapp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

/** The tab keys, in bar order. "today" is labelled Home. */
internal const val TAB_TODAY = "today"
internal const val TAB_INBOX = "inbox"
internal const val TAB_WATCH = "watch"
internal const val TAB_MOBILE = "mobile"
internal const val TAB_SHOE = "shoe"
internal const val TAB_MORE = "more"

/** Service lines that get their own tab: Watch, Mobile, Shoe in that order, at most two. */
internal fun serviceTabKeys(features: Set<String>): List<String> = buildList {
    if("watch" in features) add(TAB_WATCH)
    if("auto_key" in features) add(TAB_MOBILE)
    if("shoe" in features) add(TAB_SHOE)
}.take(2)

/** Bottom-bar tabs as (key, label): Home, Inbox, the service tabs, More. */
internal fun navTabs(features: Set<String>): List<Pair<String, String>> =
    listOf(TAB_TODAY to "Home", TAB_INBOX to "Inbox") +
        serviceTabKeys(features).map { it to when(it) { TAB_WATCH -> "Watch"; TAB_MOBILE -> "Mobile"; else -> "Shoe" } } +
        listOf(TAB_MORE to "More")

/** The route a tab opens. */
internal fun tabRoute(key: String) = when(key) { TAB_WATCH -> "watch_jobs"; TAB_MOBILE -> "auto_jobs"; TAB_SHOE -> "shoe_jobs"; else -> key }

/** Which tab a route belongs to; routes whose service has no tab (and everything else) belong to More. */
internal fun tabFor(route: String?, features: Set<String>): String {
    val key = when(route) {
        "today", "home", "dispatch", "mobileToday", "route", "dispatchPool", "new_intake" -> TAB_TODAY
        "watch_jobs" -> TAB_WATCH
        "auto_jobs" -> TAB_MOBILE
        "shoe_jobs" -> TAB_SHOE
        "inbox", "leads" -> TAB_INBOX
        else -> TAB_MORE
    }
    return if(key == TAB_WATCH || key == TAB_MOBILE || key == TAB_SHOE) (if(key in serviceTabKeys(features)) key else TAB_MORE) else key
}

/** Search affordance shared by the phone app bar and the wide top row; opens the global search route. */
@Composable fun SearchIconButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    Box(modifier.size(48.dp).semantics { contentDescription = "Search"; role = Role.Button }.clickable(onClick = onClick).testTag("app-search"), contentAlignment = Alignment.Center) {
        ToolIcon("search", size = 24.dp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Persistent top app bar for the main tab screens: wordmark left, search right, hairline below. */
@Composable fun AppHeader(onSearch: () -> Unit, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background).testTag("app-header")) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f)) { CalibreWordmark(null, Modifier.padding(bottom = 8.dp)) }
            SearchIconButton(onSearch, Modifier.statusBarsPadding().padding(end = 8.dp, top = 6.dp))
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

/** Large display-serif page title with a short accent underline, as on the web. */
@Composable fun PageTitle(text: String, modifier: Modifier = Modifier, horizontalPadding: androidx.compose.ui.unit.Dp = 20.dp) {
    Column(modifier.fillMaxWidth().padding(start = horizontalPadding, end = horizontalPadding, top = 16.dp, bottom = 12.dp)) {
        Text(text, Modifier.semantics { heading() }, style = if(LocalCalibre.current) calibreDisplayStyle(MaterialTheme.typography.headlineLarge) else MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.onSurface, maxLines = 2)
        Box(Modifier.padding(top = 8.dp).width(28.dp).height(3.dp).background(MaterialTheme.colorScheme.primary))
    }
}
