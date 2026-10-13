package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun CounterEditorScreen(resource: String, id: String, onBack: () -> Unit) {
 val vm: CounterEditorViewModel = viewModel(key = "$resource/$id", factory = CounterEditorViewModel.factory(resource,id)); val state by vm.state.collectAsStateWithLifecycle()
 Scaffold(topBar = { TopAppBar(title = { Text("Edit repair details", style = MaterialTheme.typography.headlineSmall) }, navigationIcon = { TextButton(onClick = onBack, enabled = !state.busy) { Text("Back") } }) }) { padding ->
  Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
   if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth()); state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }; if(state.saved) Text("Repair details saved.")
   val labels = listOf("job_number" to "Ticket number", "title" to "Job title *", "description" to "Requested work", "salesperson" to "Salesperson",
    "collection_date" to "Collection date (DD/MM/YYYY)", "deposit_cents" to "Deposit ($)", "pre_quote_cents" to "Pre-quote ($)", "cost_cents" to "Job cost ($)",
    "internal_notes" to "Internal shop notes", "parts_eta" to "Parts ETA (DD/MM/YYYY)")
   labels.filter { it.first in state.fields }.forEach { (key,label) -> OutlinedTextField(state.fields[key].orEmpty(), { vm.set(key,it) }, label = { Text(label) }, modifier = Modifier.fillMaxWidth(), enabled = !state.loading && !state.busy,
    keyboardOptions = KeyboardOptions(keyboardType = if(key.endsWith("_cents")) KeyboardType.Decimal else KeyboardType.Text)) }
   Text("Priority"); listOf("low", "normal", "high", "urgent").forEach { value -> Row { RadioButton(state.fields["priority"] == value, { vm.set("priority",value) }, enabled = !state.loading && !state.busy); Text(value) } }
   Text("Unsaved edits are retained on this device for this account.")
   OutlinedButton(onClick = vm::discard, enabled = !state.loading && !state.busy) { Text("Discard edits and use loaded job") }
   Button(onClick = vm::save, enabled = !state.loading && !state.busy && !state.conflict, modifier = Modifier.fillMaxWidth()) { Text("Save repair details") }
  }
 }
}
