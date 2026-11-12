package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

/** One row of a [BubbleActionsSheet]: a [label], a stable [tag] for tests, and whether it is destructive (shown in the error colour). */
data class BubbleAction(val tag: String, val label: String, val destructive: Boolean = false, val onClick: () -> Unit)

/**
 * Long-press menu for a chat bubble (Figma Messages screens): the message text as a subtitle and one big row per action.
 * Replaces the row of text links that used to sit under every hub message. Choosing an action closes the sheet first.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun BubbleActionsSheet(preview: String, actions: List<BubbleAction>, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.surface) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp).testTag("bubble-actions"), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("Message", Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(preview, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(8.dp))
            actions.forEach { a ->
                Surface({ onDismiss(); a.onClick() }, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("bubble-action-${a.tag}"), shape = RoundedCornerShape(10.dp), color = MaterialTheme.colorScheme.surface) {
                    Row(Modifier.padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(a.label, style = MaterialTheme.typography.bodyLarge, color = if(a.destructive) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
                    }
                }
            }
        }
    }
}
