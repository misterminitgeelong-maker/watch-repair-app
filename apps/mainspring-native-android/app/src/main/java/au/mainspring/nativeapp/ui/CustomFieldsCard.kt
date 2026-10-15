package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CustomFieldJobKind
import au.mainspring.nativeapp.CustomFieldsViewModel

/**
 * Custom fields section for a job detail screen (web: JobCustomFields). Self-loading: give it the job kind and id.
 * Drop into a detail screen's column: `CustomFieldsCard(CustomFieldJobKind.Watch, job.id)`.
 */
@Composable fun CustomFieldsCard(kind: CustomFieldJobKind, jobId: String, modifier: Modifier = Modifier, canEdit: Boolean = true,
    vm: CustomFieldsViewModel = viewModel(key = "custom-fields-$kind-$jobId", factory = CustomFieldsViewModel.factory(kind, jobId))) {
    val state by vm.state.collectAsStateWithLifecycle()
    var newName by rememberSaveable { mutableStateOf("") }
    var newValue by rememberSaveable { mutableStateOf("") }
    val busy = state.loading || state.saving
    Column(modifier.fillMaxWidth()) {
        SectionLabel("Custom fields")
        FlatPanel {
            if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { ErrorBanner(it, onRetry = if(state.fields.isEmpty()) vm::load else null) }
            state.info?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary) }
            if(!state.loading && state.fields.isEmpty()) Text("No custom fields yet.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if(!canEdit) state.fields.forEach { (k, v) -> DetailRow(k, v.ifBlank { "-" }) }
            else {
                state.fields.forEach { (k, v) ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        AtelierTextField(v, { vm.setValue(k, it) }, Modifier.weight(1f), enabled = !busy, label = { Text(k) }, singleLine = true)
                        TextButton({ vm.remove(k) }, enabled = !busy) { Text("Remove") }
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    AtelierTextField(newName, { newName = it }, Modifier.weight(1f), enabled = !busy, label = { Text("Field name") }, singleLine = true)
                    AtelierTextField(newValue, { newValue = it }, Modifier.weight(1f), enabled = !busy, label = { Text("Value") }, singleLine = true)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SecondaryAction({ if(vm.add(newName, newValue)) { newName = ""; newValue = "" } }, enabled = !busy && newName.isNotBlank()) { Text("Add") }
                    PrimaryAction(vm::save, enabled = !busy && state.dirty) { Text(if(state.saving) "Saving..." else "Save fields") }
                }
            }
        }
    }
}
