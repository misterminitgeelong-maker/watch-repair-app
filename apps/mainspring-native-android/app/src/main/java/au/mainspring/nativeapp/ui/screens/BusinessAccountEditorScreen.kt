package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BusinessAccountEditorScreen(id: String, onBack: () -> Unit, onOpenAccount: (String) -> Unit,
    vm: BusinessAccountEditorViewModel = viewModel(key = id.ifBlank { "new" }, factory = BusinessAccountEditorViewModel.factory(id))) {
    val state by vm.state.collectAsStateWithLifecycle()
    var confirm by remember { mutableStateOf(false) }
    val enabled = !state.loading && !state.busy && !state.uncertain && state.createdId == null && TokenStore.canManageInvoices()
    BackHandler { if(!state.busy) onBack() }
    Scaffold(topBar = { TopAppBar(title = { Text(if(id.isBlank()) "New business account" else "Edit business account") }, navigationIcon = { TextButton(onClick = onBack, enabled = !state.busy) { Text("Back") } }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if(state.saved) Text("Account saved.")
            state.createdId?.let { created ->
                Button(onClick = { onOpenAccount(created) }) { Text("Open saved account") }
                OutlinedButton(onClick = vm::startAnother, enabled = !state.busy) { Text("Start another account") }
            }
            if(state.uncertain) {
                Text("Check the account directory before creating this account again.")
                OutlinedButton(onClick = { vm.refresh() }, enabled = !state.loading && !state.busy) { Text("Refresh existing accounts") }
                state.accounts.forEach { account -> OutlinedButton(onClick = { vm.useExisting(account.id) }, enabled = state.historyChecked && !state.busy) { Text("Use existing ${account.name}") } }
                OutlinedButton(onClick = vm::checkedAccounts, enabled = state.historyChecked && !state.busy) { Text("I checked that this account was not saved") }
            }
            listOf("name" to "Account name *", "account_code" to "Account code", "contact_name" to "Contact name", "contact_email" to "Contact email",
                "contact_phone" to "Contact phone", "billing_address" to "Billing address", "payment_terms_days" to "Payment terms (days)", "notes" to "Notes",
                "fleet_size" to "Fleet size", "primary_contact_name" to "Primary contact name", "primary_contact_phone" to "Primary contact phone",
                "credit_limit" to "Credit limit (whole dollars)", "account_notes" to "Account notes").forEach { (key,label) ->
                OutlinedTextField(state.fields[key].orEmpty(), { vm.set(key,it) }, label = { Text(label) }, enabled = enabled, modifier = Modifier.fillMaxWidth())
            }
            Text("Account type", style = MaterialTheme.typography.titleMedium)
            (listOf("") + BusinessAccountEditorViewModel.accountTypes).forEach { option -> Row(Modifier.fillMaxWidth().selectable(state.fields["account_type"].orEmpty() == option, enabled = enabled, role = Role.RadioButton, onClick = { vm.set("account_type",option) })) {
                RadioButton(state.fields["account_type"].orEmpty() == option, null, enabled = enabled)
                Text(option.ifBlank { "Not specified" }, modifier = Modifier.padding(top = 12.dp))
            } }
            Text("Billing cycle", style = MaterialTheme.typography.titleMedium)
            (listOf("") + BusinessAccountEditorViewModel.billingCycles).forEach { option -> Row(Modifier.fillMaxWidth().selectable(state.fields["billing_cycle"].orEmpty() == option, enabled = enabled, role = Role.RadioButton, onClick = { vm.set("billing_cycle",option) })) {
                RadioButton(state.fields["billing_cycle"].orEmpty() == option, null, enabled = enabled)
                Text(option.ifBlank { "Not specified" }, modifier = Modifier.padding(top = 12.dp))
            } }
            if(id.isNotBlank()) Row { Checkbox(state.fields["is_active"] == "true", { vm.set("is_active", it.toString()) }, enabled = enabled); Text("Active account", Modifier.padding(top = 12.dp)) }
            if(state.createdId == null && !state.uncertain) {
                Text("Your unsaved edits are retained for this account on this device.")
                OutlinedButton(onClick = { if(id.isBlank()) vm.startAnother() else vm.refresh(discard = true) }, enabled = !state.busy && !state.loading) { Text(if(id.isBlank()) "Discard draft" else "Discard edits and reload account") }
                Button(onClick = { confirm = true }, enabled = enabled && !state.conflict && state.fields["name"].orEmpty().isNotBlank()) { Text(if(id.isBlank()) "Create account" else "Save account changes") }
            }
        }
    }
    if(confirm) AlertDialog(onDismissRequest = { confirm = false }, title = { Text(if(id.isBlank()) "Create business account?" else "Save account changes?") },
        text = { Text("Save the details for ${state.fields["name"].orEmpty()}.") },
        confirmButton = { TextButton(onClick = { confirm = false; vm.save() }) { Text("Confirm account save") } },
        dismissButton = { TextButton(onClick = { confirm = false }) { Text("Cancel") } })
}
