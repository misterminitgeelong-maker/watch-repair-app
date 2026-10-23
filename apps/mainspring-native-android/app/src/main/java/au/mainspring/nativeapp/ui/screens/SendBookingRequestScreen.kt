package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.SendBookingRequestViewModel
import au.mainspring.nativeapp.ui.AtelierTextField
import au.mainspring.nativeapp.ui.BackLargeHeader
import au.mainspring.nativeapp.ui.ErrorBanner
import au.mainspring.nativeapp.ui.PrimaryAction
import au.mainspring.nativeapp.ui.SecondaryAction

@Composable
fun SendBookingRequestScreen(onBack: () -> Unit, onDone: () -> Unit = onBack, viewModel: SendBookingRequestViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val clipboard = LocalClipboardManager.current
    var copied by remember { mutableStateOf(false) }
    BackHandler { if (!state.busy) onBack() }
    Scaffold(topBar = { BackLargeHeader("Today", "Mobile services", "Send booking request", onBack, backEnabled = !state.busy) }) { padding ->
        Column(
            Modifier.padding(padding).consumeWindowInsets(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { ErrorBanner(it) }
            val job = state.result
            if (job != null) {
                Text("Booking request sent", style = MaterialTheme.typography.titleMedium)
                Text("Job ${job.jobNumber} was created for ${job.customerName ?: "the customer"}${job.customerPhone?.let { " ($it)" }.orEmpty()}. " +
                    "Mainspring texts them a link to add vehicle details and pick a time. Delivery is not reported back, so ask the customer if they do not see it.")
                SecondaryAction(onClick = { clipboard.setText(AnnotatedString(job.jobNumber)); copied = true }, modifier = Modifier.fillMaxWidth()) {
                    Text(if (copied) "Job number copied" else "Copy job number")
                }
                PrimaryAction(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Done") }
                SecondaryAction(onClick = { copied = false; viewModel.startAnother() }, modifier = Modifier.fillMaxWidth()) { Text("Send another") }
            } else {
                Text("Enter the customer's mobile number. They will receive an SMS with a link to fill in their vehicle details and preferred date and time.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (state.uncertain) {
                    Text("The previous request may already have been sent. Check with the customer before sending again.")
                    SecondaryAction(onClick = viewModel::checkedWithCustomer, enabled = !state.busy) { Text("I have checked with the customer") }
                }
                AtelierTextField(state.phone, viewModel::phone, singleLine = true, enabled = !state.busy && !state.uncertain, modifier = Modifier.fillMaxWidth(),
                    label = { Text("Mobile number *") }, placeholder = { Text("e.g. 0412 345 678") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone))
                AtelierTextField(state.name, viewModel::name, singleLine = true, enabled = !state.busy && !state.uncertain, modifier = Modifier.fillMaxWidth(),
                    label = { Text("Customer name (optional)") }, placeholder = { Text("e.g. Sam Taylor") })
                PrimaryAction(onClick = viewModel::send, enabled = !state.busy && !state.uncertain && state.phone.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.busy) "Sending..." else "Send SMS")
                }
            }
        }
    }
}
