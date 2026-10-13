package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ArrivalMessageScreen(id: String, onBack: () -> Unit, vm: ArrivalMessageViewModel = viewModel(key = id, factory = ArrivalMessageViewModel.factory(id))) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var confirm by remember { mutableStateOf(false) }
    var dialError by remember { mutableStateOf<String?>(null) }
    BackHandler { if(!state.busy) onBack() }
    Scaffold(topBar = { TopAppBar(title = { Text("Arrival message", style = MaterialTheme.typography.titleLarge) }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack, enabled = !state.busy) }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }; dialError?.let { Text(it, color = MaterialTheme.colorScheme.error) }; state.info?.let { Text(it) }
            state.customer?.let { customer ->
                Text(customer.fullName, style = MaterialTheme.typography.titleMedium)
                customer.phone?.takeIf { it.isNotBlank() }?.let { phone ->
                    Text(phone)
                    OutlinedButton(onClick = { try { context.startActivity(Intent(Intent.ACTION_DIAL,Uri.fromParts("tel",phone,null))) } catch(_: android.content.ActivityNotFoundException) { dialError = "No phone app is available on this device." } }) { Text("Call customer") }
                }
            }
            if(state.uncertain) {
                Text("The previous message may already have been sent. Check with the customer before repeating it.")
                OutlinedButton(onClick = vm::checkedCustomer, enabled = !state.loading && !state.busy && state.customer != null) { Text("I have checked with the customer") }
            }
            if(state.draft.accepted) {
                Text("The last arrival request was accepted.")
                OutlinedButton(onClick = vm::startUpdatedWindow, enabled = !state.busy) { Text("Send an updated arrival window") }
            }
            OutlinedTextField(state.draft.window, vm::window, label = { Text("Arrival window, e.g. 9–11 am") }, enabled = !state.busy && !state.uncertain && !state.draft.accepted, modifier = Modifier.fillMaxWidth())
            Text("Your technician is on the way and will arrive between ${state.draft.window.ifBlank { "[arrival window]" }}. Please ensure someone is available at the vehicle.")
            Button(onClick = { confirm = true }, enabled = !state.loading && !state.busy && !state.uncertain && !state.draft.accepted && state.draft.window.isNotBlank() && !state.customer?.phone.isNullOrBlank() && TokenStore.canWorkJobs()) { Text("Send arrival SMS") }
            androidx.compose.material3.TextButton(onClick = vm::refresh, enabled = !state.loading && !state.busy) { Text("Refresh") }
        }
    }
    if(confirm) AlertDialog(onDismissRequest = { confirm = false }, title = { Text("Send arrival SMS?", style = MaterialTheme.typography.headlineSmall) }, text = { Text("Request an arrival SMS to ${state.customer?.phone} for ${state.draft.window}.") },
        confirmButton = { TextButton(onClick = { confirm = false; vm.send() }) { Text("Confirm arrival message") } },
        dismissButton = { TextButton(onClick = { confirm = false }) { Text("Cancel") } })
}
