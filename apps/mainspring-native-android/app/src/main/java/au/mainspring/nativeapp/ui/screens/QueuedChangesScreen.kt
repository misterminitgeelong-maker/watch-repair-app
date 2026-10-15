package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import au.mainspring.nativeapp.offline.OfflineSync
import au.mainspring.nativeapp.ui.*

/** Lists changes waiting to sync (discardable) and changes the server rejected ("Needs attention"). */
@Composable fun QueuedChangesScreen(onBack: () -> Unit) {
    val snap by OfflineSync.queue.state.collectAsStateWithLifecycle()
    val online by au.mainspring.nativeapp.ConnectivityMonitor.online.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        BackLargeHeader("More", "Offline", "Queued changes", onBack)
        if (snap.pending.isEmpty() && snap.attention.isEmpty()) {
            EmptyState("Nothing waiting", "Status changes and notes made while offline appear here until they sync.")
            return@Column
        }
        LazyColumn(Modifier.weight(1f).testTag("queued-changes-list"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (snap.pending.isNotEmpty()) {
                item {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        SectionLabel("Waiting to sync (${snap.pending.size})", Modifier.weight(1f))
                        TextButton(onClick = { OfflineSync.requestReplay() }, enabled = online, modifier = Modifier.testTag("sync-now")) { Text("Sync now") }
                    }
                }
                items(snap.pending, key = { it.id }) { w ->
                    FlatPanel {
                        Text(w.summary, style = MaterialTheme.typography.titleSmall)
                        if (w.attempts > 0) Text("Tried ${w.attempts} time${if (w.attempts == 1) "" else "s"}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        TextButton(onClick = { OfflineSync.queue.discard(w.id) }, modifier = Modifier.testTag("discard-${w.id}")) { Text("Discard") }
                    }
                }
            }
            if (snap.attention.isNotEmpty()) {
                item {
                    Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        SectionLabel("Needs attention (${snap.attention.size})", Modifier.weight(1f))
                        TextButton(onClick = { OfflineSync.queue.dismissAllAttention() }) { Text("Dismiss all") }
                    }
                }
                items(snap.attention, key = { it.item.id }) { a ->
                    FlatPanel {
                        Text(a.item.summary, style = MaterialTheme.typography.titleSmall)
                        Text(a.reason, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                        TextButton(onClick = { OfflineSync.queue.dismissAttention(a.item.id) }, modifier = Modifier.testTag("dismiss-${a.item.id}")) { Text("Dismiss") }
                    }
                }
            }
        }
    }
}
