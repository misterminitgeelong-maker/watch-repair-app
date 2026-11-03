package au.mainspring.nativeapp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.minimumInteractiveComponentSize
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import au.mainspring.nativeapp.ConnectivityMonitor
import kotlinx.coroutines.delay

/** Slim bar shown while the device is offline, with a brief "Back online" confirmation afterwards. */
@Composable
fun ConnectivityBanner(modifier: Modifier = Modifier, onOpenQueue: (() -> Unit)? = null, onVisibleChange: (Boolean) -> Unit = {}) {
    val queued by au.mainspring.nativeapp.offline.OfflineSync.queue.state.collectAsStateWithLifecycle()
    val pending = queued.pending.size; val attention = queued.attention.size
    val online by ConnectivityMonitor.online.collectAsStateWithLifecycle()
    var wasOffline by remember { mutableStateOf(false) }
    var showRestored by remember { mutableStateOf(false) }
    LaunchedEffect(online) {
        if (!online) { wasOffline = true; showRestored = false }
        else if (wasOffline) { wasOffline = false; showRestored = true; delay(2500); showRestored = false }
    }
    val visible = !online || showRestored || pending > 0 || attention > 0
    SideEffect { onVisibleChange(visible) }
    if (online && !showRestored) {
        if (pending > 0 || attention > 0) QueueChipRow(pending, attention, onOpenQueue, modifier)
        return
    }
    val offline = !online
    Row(
        modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite }.background(if (offline) BannerAmber else BannerGreen).statusBarsPadding().padding(horizontal = 20.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        MonoLabel(if (offline) "Offline" else "Online", color = Calibre.Ink)
        Text(
            if (offline) "You are offline. Job status changes and notes are saved and will sync." else "Back online",
            Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = Calibre.Ink,
        )
        if (pending > 0) QueueChip(pending, onOpenQueue)
    }
}

private val BannerAmber = Color(0xFFFFE9B0)
private val BannerGreen = Color(0xFFDDEBE3)

fun pendingChangesLabel(count: Int) = if (count == 1) "1 change waiting to sync" else "$count changes waiting to sync"

@Composable private fun QueueChip(pending: Int, onOpenQueue: (() -> Unit)?) {
    Text(pendingChangesLabel(pending), Modifier.testTag("pending-changes-chip").let { if (onOpenQueue != null) it.minimumInteractiveComponentSize().clickable(role = androidx.compose.ui.semantics.Role.Button, onClick = onOpenQueue) else it }
        .background(Calibre.Ink.copy(alpha = 0.10f)).padding(horizontal = 8.dp, vertical = 4.dp),
        style = MaterialTheme.typography.labelSmall, color = Calibre.Ink)
}

@Composable private fun QueueChipRow(pending: Int, attention: Int, onOpenQueue: (() -> Unit)?, modifier: Modifier) {
    Row(modifier.fillMaxWidth().semantics { liveRegion = LiveRegionMode.Polite }.background(BannerAmber).statusBarsPadding().padding(horizontal = 20.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        MonoLabel("Sync", color = Calibre.Ink)
        if (pending > 0) QueueChip(pending, onOpenQueue)
        if (attention > 0) Text("$attention need attention", Modifier.testTag("attention-chip").let { if (onOpenQueue != null) it.minimumInteractiveComponentSize().clickable(role = androidx.compose.ui.semantics.Role.Button, onClick = onOpenQueue) else it },
            style = MaterialTheme.typography.bodySmall, color = Calibre.Ink)
    }
}
