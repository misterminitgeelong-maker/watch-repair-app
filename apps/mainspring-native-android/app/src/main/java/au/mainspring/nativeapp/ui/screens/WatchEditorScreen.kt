package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.WatchEditorViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WatchEditorScreen(customerId: String, id: String, onBack: () -> Unit, onCustomer: () -> Unit,
    model: WatchEditorViewModel = viewModel(factory = WatchEditorViewModel.factory(customerId,id))) {
    val state by model.state.collectAsStateWithLifecycle()
    var review by remember { mutableStateOf(false) }
    BackHandler(state.busy) {}
    Scaffold(topBar = { TopAppBar(title = { Text(if(id.isBlank()) "Add watch" else "Edit watch") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onBack, enabled = !state.busy) }) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if(state.saved) {
                Text(if(id.isBlank()) "Watch ready" else "Watch updated")
                OutlinedButton(onCustomer) { Text("Return to customer watches") }
                if(id.isBlank()) TextButton(model::another) { Text("Add another watch") }
            }
            if(state.uncertain) {
                Text("Creation has no confirmed result. Check the customer's watches before trying again.")
                OutlinedButton(model::review, enabled = !state.loading) { Text("Review saved watches") }
                state.matches.forEach { watch -> OutlinedButton({ model.useExisting(watch.id) }) { Text("Use ${listOfNotNull(watch.brand,watch.model,watch.serialNumber).joinToString(" · ").ifBlank { "Watch" }}") } }
                TextButton({ review = true }, enabled = state.reviewed && !state.loading) { Text("Reviewed watches; creation did not save") }
            }
            listOf("brand" to "Brand", "model" to "Model", "serial_number" to "Serial number", "movement_type" to "Movement type", "condition_notes" to "Condition notes").forEach { (key,label) ->
                OutlinedTextField(state.fields[key].orEmpty(), { model.set(key,it) }, label = { Text(label) }, modifier = Modifier.fillMaxWidth(), enabled = !state.loading && !state.busy && !state.uncertain && state.createdId == null)
            }
            if(id.isNotBlank()) OutlinedButton({ model.load(discard = true) }, enabled = !state.loading && !state.busy) { Text("Discard edits and load latest watch") }
            Button(model::save, enabled = !state.loading && !state.busy && !state.uncertain && !state.conflict && state.createdId == null) { Text(if(id.isBlank()) "Save new watch" else "Save watch changes") }
        }
    }
    if(review) AlertDialog(onDismissRequest = { review = false }, title = { Text("Confirm watch review", style = MaterialTheme.typography.headlineSmall) }, text = { Text("I checked all refreshed watches for this customer and confirmed the previous creation did not save. Allow another attempt?") },
        confirmButton = { TextButton({ review = false; model.reviewedNotCreated() }) { Text("Confirm review") } }, dismissButton = { TextButton({ review = false }) { Text("Cancel") } })
}
