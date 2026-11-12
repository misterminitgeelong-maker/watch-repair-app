package au.mainspring.nativeapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * "Change status" bottom sheet from the seamless-pass designs (Figma screen B): big selectable status rows, the two note fields,
 * and one "Update status" button. Picking a row only selects it; nothing is applied until the button is pressed.
 * [options] are (stored key, label); the [current] status is shown but cannot be chosen again.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun StatusChangeSheet(
    subtitle: String,
    options: List<Pair<String, String>>,
    current: String?,
    note: String,
    onNote: (String) -> Unit,
    customerNote: String,
    onCustomerNote: (String) -> Unit,
    customerNoteLabel: String,
    customerNoteHint: String,
    onConfirm: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var picked by rememberSaveable { mutableStateOf<String?>(null) }
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.surface) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp).verticalScroll(rememberScrollState()).testTag("status-sheet"), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("Change status", Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            options.forEach { (key, label) ->
                val isCurrent = key == current
                val on = key == picked
                Surface({ picked = key }, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("status-option-$key").semantics { this.selected = on; role = Role.RadioButton },
                    enabled = !isCurrent, shape = RoundedCornerShape(10.dp),
                    color = if(on) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
                    border = if(on) BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null) {
                    Row(Modifier.padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        RadioButton(on || isCurrent, onClick = null, enabled = !isCurrent)
                        Text(label + if(isCurrent) " (current)" else "", Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge,
                            fontWeight = if(on) FontWeight.Bold else FontWeight.Normal,
                            color = if(isCurrent) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            AtelierTextField(value = note, onValueChange = onNote, label = { Text("Note (optional)") }, modifier = Modifier.fillMaxWidth(), singleLine = false, maxLines = 3)
            Spacer(Modifier.height(8.dp))
            AtelierTextField(value = customerNote, onValueChange = onCustomerNote, label = { Text(customerNoteLabel) }, modifier = Modifier.fillMaxWidth(), singleLine = false, maxLines = 3)
            Text(customerNoteHint, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(12.dp))
            Button({ picked?.let(onConfirm) }, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("status-sheet-update"), enabled = picked != null, shape = RoundedCornerShape(12.dp)) { Text("Update status") }
        }
    }
}
