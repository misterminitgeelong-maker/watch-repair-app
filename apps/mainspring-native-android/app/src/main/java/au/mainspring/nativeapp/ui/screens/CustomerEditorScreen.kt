package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CustomerEditorViewModel
import au.mainspring.nativeapp.TokenStore
import com.google.gson.JsonObject
import com.google.gson.JsonParser

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerEditorScreen(customerId: String, onBack: () -> Unit, onOpenCustomer: (String) -> Unit = {}, vm: CustomerEditorViewModel = viewModel(key = customerId, factory = CustomerEditorViewModel.factory(customerId))) {
    val state by vm.state.collectAsStateWithLifecycle()
    val drafts = remember(customerId) { TokenStore.bindDrafts() }
    val draftKey = "customer-editor/${customerId.ifBlank { "new" }}"
    val draft = remember(draftKey) { try { JsonParser.parseString(drafts.loadMessageDraft(draftKey)).asJsonObject } catch(_: Exception) { null } }
    fun initial(key: String) = draft?.get(key)?.asString.orEmpty()
    var name by rememberSaveable { mutableStateOf(initial("name")) }; var email by rememberSaveable { mutableStateOf(initial("email")) }
    var phone by rememberSaveable { mutableStateOf(initial("phone")) }; var address by rememberSaveable { mutableStateOf(initial("address")) }
    var notes by rememberSaveable { mutableStateOf(initial("notes")) }; var filled by rememberSaveable { mutableStateOf(draft != null) }
    LaunchedEffect(name, email, phone, address, notes, filled, state.saved) {
        if(state.saved) drafts.saveMessageDraft(draftKey, "")
        else if(filled || customerId.isBlank()) drafts.saveMessageDraft(draftKey, JsonObject().apply { addProperty("name", name); addProperty("email", email); addProperty("phone", phone); addProperty("address", address); addProperty("notes", notes) }.toString())
    }
    LaunchedEffect(state.customer, state.revision) {
        if(!filled || state.revision > 0) state.customer?.let { c -> name = c.fullName; email = c.email.orEmpty(); phone = c.phone.orEmpty(); address = c.address.orEmpty(); notes = c.notes.orEmpty(); filled = true }
        if(customerId.isBlank() && state.revision > 0 && state.customer == null) { name = ""; email = ""; phone = ""; address = ""; notes = ""; filled = false }
    }
    Scaffold(topBar = { TopAppBar(title = { Text(if(customerId.isBlank()) "New customer" else "Edit customer") }, navigationIcon = { TextButton(onClick = onBack, enabled = !state.saving) { Text("Back") } }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if(state.loading || state.saving) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            if(customerId.isNotBlank()) OutlinedButton(onClick = { vm.load(discard = true) }, enabled = !state.loading && !state.saving) { Text("Discard edits and load latest customer") }
            if(state.saved) { Text(if(customerId.isBlank()) "Customer created" else "Customer updated"); state.customer?.let { OutlinedButton(onClick = { onOpenCustomer(it.id) }) { Text("Open customer profile") } }; if(customerId.isBlank()) TextButton(vm::startAnother) { Text("Start another customer") } }
            if(state.unknown) {
                OutlinedButton(onClick = { vm.reviewRecords(name) }, enabled = !state.loading) { Text("Check existing customers") }
                Text("Up to 200 matching customers are shown. Refine the name if needed.")
                state.matches.forEach { customer -> OutlinedButton(onClick = { vm.useExisting(customer.id) }) { Text("Use ${customer.fullName} · ${customer.phone.orEmpty()}") } }
                OutlinedButton(onClick = vm::confirmNotSaved, enabled = state.reviewed && !state.loading) { Text("I checked: this customer was not saved") }
            }
            val editable = !state.saving && !state.loading && !state.unknown && !(customerId.isBlank() && state.saved)
            OutlinedTextField(name, { name = it; vm.changed() }, label = { Text("Name *") }, enabled = editable, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(phone, { phone = it; vm.changed() }, label = { Text("Phone") }, enabled = editable, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(email, { email = it; vm.changed() }, label = { Text("Email") }, enabled = editable, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(address, { address = it; vm.changed() }, label = { Text("Address") }, enabled = editable, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(notes, { notes = it; vm.changed() }, label = { Text("Notes") }, enabled = editable, modifier = Modifier.fillMaxWidth())
            Button(onClick = { vm.save(name, email, phone, address, notes) }, enabled = !state.saving && !state.loading && !state.unknown && !state.conflict && (if(customerId.isBlank()) !state.saved else state.customer != null)) { Text(if(customerId.isBlank()) "Create customer" else "Save changes") }
        }
    }
}
