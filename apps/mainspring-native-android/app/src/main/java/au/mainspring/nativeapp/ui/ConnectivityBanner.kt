package au.mainspring.nativeapp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import au.mainspring.nativeapp.ConnectivityMonitor
import kotlinx.coroutines.delay

/** Slim bar shown while the device is offline, with a brief "Back online" confirmation afterwards. */
@Composable
fun ConnectivityBanner(modifier: Modifier = Modifier) {
    val online by ConnectivityMonitor.online.collectAsStateWithLifecycle()
    var wasOffline by remember { mutableStateOf(false) }
    var showRestored by remember { mutableStateOf(false) }
    LaunchedEffect(online) {
        if (!online) { wasOffline = true; showRestored = false }
        else if (wasOffline) { wasOffline = false; showRestored = true; delay(2500); showRestored = false }
    }
    if (online && !showRestored) return
    val offline = !online
    Row(
        modifier.fillMaxWidth().background(if (offline) Calibre.Ink else Calibre.Forest).padding(horizontal = 20.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        MonoLabel(if (offline) "Offline" else "Online", color = Color.White)
        Text(
            if (offline) "You are offline. Changes will fail until you reconnect." else "Back online",
            Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = Color.White,
        )
    }
}
