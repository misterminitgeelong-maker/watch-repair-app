package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.MOBILE_JOB_TYPES
import au.mainspring.nativeapp.api.MOBILE_LEAD_SOURCES
import au.mainspring.nativeapp.api.MOBILE_PRIORITIES
@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable fun MobileEditorScreen(id: String, onBack: () -> Unit, vm: MobileEditorViewModel = viewModel(key = id, factory = MobileEditorViewModel.factory(id))) {
 val state by vm.state.collectAsStateWithLifecycle()
 var teamOpen by remember { mutableStateOf(false) }
 var accountOpen by remember { mutableStateOf(false) }
 androidx.activity.compose.BackHandler(state.busy) {}
 Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Edit mobile job") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack, enabled = !state.busy) }) }) { padding ->
  Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
   if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
   state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }; if(state.saved) Text("Job changes saved.")
   listOf("title" to "Job title *", "description" to "Requested work", "job_address" to "Job address", "scheduled_at" to "Booking (DD/MM/YYYY HH:mm)",
    "vehicle_make" to "Vehicle make", "vehicle_model" to "Vehicle model", "vehicle_year" to "Vehicle year", "registration_plate" to "Registration plate", "vin" to "VIN",
    "key_type" to "Key type", "blade_code" to "Blade code", "chip_type" to "Chip type", "key_quantity" to "Key quantity", "tech_notes" to "Technician notes").forEach { (key, label) ->
    au.mainspring.nativeapp.ui.AtelierTextField(state.fields[key].orEmpty(), { vm.set(key, it) }, label = { Text(label) }, modifier = Modifier.fillMaxWidth(), enabled = !state.loading && !state.busy)
   }
   Text("Booking timezone: ${TokenStore.calendarTimezone()}")
   val editable = !state.loading && !state.busy
   au.mainspring.nativeapp.ui.SectionLabel("Job type")
   val currentType = state.fields["job_type"].orEmpty()
   FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
    (MOBILE_JOB_TYPES + listOfNotNull(currentType.takeIf { it.isNotBlank() && it !in MOBILE_JOB_TYPES })).forEach { type ->
     au.mainspring.nativeapp.ui.AtelierChip(currentType == type, { vm.set("job_type", if(currentType == type) "" else type) }, enabled = editable, label = { Text(type) })
    }
   }
   au.mainspring.nativeapp.ui.SectionLabel("Priority")
   FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
    MOBILE_PRIORITIES.forEach { p -> au.mainspring.nativeapp.ui.AtelierChip(state.fields["priority"] == p, { vm.set("priority", p) }, enabled = editable, label = { Text(au.mainspring.nativeapp.ui.statusLabel(p)) }) }
   }
   au.mainspring.nativeapp.ui.AtelierTextField(state.fields["deposit"].orEmpty(), { vm.set("deposit", it) }, label = { Text("Deposit ($)") }, modifier = Modifier.fillMaxWidth(), enabled = editable)
   au.mainspring.nativeapp.ui.SectionLabel("Job source (commission tier)")
   val currentSource = state.fields["commission_lead_source"].orEmpty()
   FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
    (MOBILE_LEAD_SOURCES + listOfNotNull(currentSource.takeIf { s -> s.isNotBlank() && MOBILE_LEAD_SOURCES.none { it.first == s } }?.let { it to au.mainspring.nativeapp.ui.statusLabel(it) })).forEach { (value, label) ->
     au.mainspring.nativeapp.ui.AtelierChip(currentSource == value, { vm.set("commission_lead_source", value) }, enabled = editable, label = { Text(label) })
    }
   }
   Text("Billing account", style = MaterialTheme.typography.titleMedium)
   val selectedAccount = state.fields["customer_account_id"].orEmpty()
   Text(if(selectedAccount.isBlank()) "No billing account" else state.accounts.firstOrNull { it.id == selectedAccount }?.name ?: "Current billing account")
   state.accountError?.let { Text(it) }
   if(state.accounts.isNotEmpty() || selectedAccount.isNotBlank()) OutlinedButton({ accountOpen = true }, enabled = !state.loading && !state.busy && TokenStore.canWorkJobs()) { Text("Change billing account") }
   Text("Assigned technician", style = MaterialTheme.typography.titleMedium)
   val selectedUser = state.fields["assigned_user_id"].orEmpty()
   Text(if(selectedUser.isBlank()) "Unassigned" else state.users.firstOrNull { it.id == selectedUser }?.name ?: "Current assigned team member")
   state.teamError?.let { Text(it) }
   OutlinedButton(onClick = { teamOpen = true }, enabled = !state.loading && !state.busy && TokenStore.canWorkJobs()) { Text("Change technician") }
   Text("Programming status", style = MaterialTheme.typography.titleMedium)
   listOf("pending", "in_progress", "programmed", "failed", "not_required").forEach { value ->
    Row { RadioButton(state.fields["programming_status"] == value, { vm.set("programming_status", value) }, enabled = !state.loading && !state.busy); Text(au.mainspring.nativeapp.ui.statusLabel(value)) }
   }
   Text("Your unsaved edits are saved on this device for this account.")
   OutlinedButton(onClick = vm::discardDraft, enabled = !state.loading && !state.busy) { Text("Discard edits and use loaded job") }
   Button(onClick = vm::save, enabled = !state.loading && !state.busy && TokenStore.canWorkJobs(), modifier = Modifier.fillMaxWidth()) { Text("Save job changes") }
  }
 }
 if(accountOpen) AlertDialog(onDismissRequest = { accountOpen = false }, title = { Text("Choose billing account") }, text = {
  Column(Modifier.verticalScroll(rememberScrollState())) {
   TextButton({ vm.set("customer_account_id", ""); accountOpen = false }) { Text("No billing account") }
   state.accounts.filter { it.active }.forEach { account -> TextButton({ vm.set("customer_account_id", account.id); accountOpen = false }) { Text(account.name) } }
  }
 }, confirmButton = { TextButton({ accountOpen = false }) { Text("Done") } })
 if(teamOpen) AlertDialog(onDismissRequest = { teamOpen = false }, title = { Text("Choose technician") }, text = {
  Column(Modifier.verticalScroll(rememberScrollState())) {
   TextButton(onClick = { vm.set("assigned_user_id", ""); teamOpen = false }) { Text("Unassigned") }
   state.users.filter { it.active }.forEach { user -> TextButton(onClick = { vm.set("assigned_user_id", user.id); teamOpen = false }) { Text(user.name) } }
  }
 }, confirmButton = { TextButton(onClick = { teamOpen = false }) { Text("Done") } })
}
