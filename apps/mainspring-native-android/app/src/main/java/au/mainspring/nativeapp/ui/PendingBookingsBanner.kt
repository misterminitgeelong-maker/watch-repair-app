package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.PendingBookingsViewModel

/** "N booking requests waiting" entry shown atop the job board; renders nothing when there are none. */
@Composable fun PendingBookingsBanner(onOpen: () -> Unit, modifier: Modifier = Modifier, model: PendingBookingsViewModel = viewModel()) {
    val count by model.pending.collectAsStateWithLifecycle()
    RefreshOnResume(model::refresh)
    if(count <= 0) return
    ListCard(onOpen, modifier) {
        Text(if(count == 1) "1 booking request waiting" else "$count booking requests waiting", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
        Text("Accept or decline requests from shops.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
