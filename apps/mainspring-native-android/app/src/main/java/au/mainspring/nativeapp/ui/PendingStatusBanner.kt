package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import au.mainspring.nativeapp.offline.OfflineSync
import au.mainspring.nativeapp.offline.pendingStatusFor

/** Shown on a job screen while a status change made offline is still waiting to sync. Renders nothing otherwise. */
@Composable fun PendingStatusBanner(jobId: String, modifier: Modifier = Modifier) {
    val snap by OfflineSync.queue.state.collectAsStateWithLifecycle()
    val pending = snap.pendingStatusFor(jobId) ?: return
    Surface(modifier.fillMaxWidth().testTag("pending-status-banner"), color = MaterialTheme.colorScheme.secondaryContainer, shape = MaterialTheme.shapes.medium) {
        Text(
            "${OfflineSync.SAVED_OFFLINE_MESSAGE}: status will change to ${pending.replace('_', ' ')}",
            Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onSecondaryContainer, style = MaterialTheme.typography.bodyMedium,
        )
    }
}
