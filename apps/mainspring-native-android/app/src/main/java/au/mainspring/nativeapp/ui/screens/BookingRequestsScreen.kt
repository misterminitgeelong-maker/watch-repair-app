package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun BookingRequestsScreen(canRequest: Boolean, onBack: () -> Unit, onOpenJob: (String) -> Unit, vm: BookingViewModel = viewModel()) {
 val state by vm.state.collectAsStateWithLifecycle(); var creating by rememberSaveable { mutableStateOf(false) }
 var confirm by remember { mutableStateOf<Pair<String,String>?>(null) }; var reason by rememberSaveable { mutableStateOf("") }
 val enabled = !state.loading && !state.busy
 val tenant = TokenStore.currentTenantId()
 Scaffold(topBar = { TopAppBar(title = { Text("Mobile booking requests", style = MaterialTheme.typography.headlineSmall) }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
  LazyColumn(Modifier.padding(padding).fillMaxSize().imePadding(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
   item {
    if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }; state.info?.let { Text(it) }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
     OutlinedButton(onClick = vm::refresh, enabled = enabled) { Text("Refresh requests") }
     if(canRequest) Button(onClick = { creating = !creating }, enabled = enabled) { Text(if(creating) "Hide form" else "New request") }
    }
    if(state.uncertain) OutlinedButton(onClick = vm::checkedHistory, enabled = enabled && state.historyChecked) { Text("I checked for the saved request") }
   }
   if(creating && canRequest) item {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
     Text("Request a mobile visit", style = MaterialTheme.typography.titleLarge)
     listOf("customer_name" to "Customer name *", "phone" to "Customer phone", "email" to "Customer email", "suburb" to "Suburb *", "job_address" to "Visit address *",
      "vehicle_make" to "Vehicle make", "vehicle_model" to "Vehicle model", "registration_plate" to "Registration plate", "job_type" to "Requested service",
      "preferred_scheduled_at" to "Preferred time (DD/MM/YYYY HH:mm)", "notes" to "Notes").forEach { (key, label) ->
      OutlinedTextField(state.fields[key].orEmpty(), { vm.set(key, it) }, label = { Text(label) }, modifier = Modifier.fillMaxWidth(), enabled = enabled)
     }
     Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
      listOf("ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA").forEach { value -> FilterChip(state.fields["state_code"] == value, { vm.set("state_code", value) }, label = { Text(value) }, enabled = enabled) }
     }
     Text("Visit location")
     listOf("customer_site" to "Customer's address", "at_shop" to "At this shop").forEach { (key, label) -> Row { RadioButton(state.fields["visit_location_type"].orEmpty().ifBlank { "customer_site" } == key, { vm.set("visit_location_type", key) }, enabled = enabled); Text(label) } }
     Text("Operator")
     Row { RadioButton(state.fields["target_operator_tenant_id"].isNullOrBlank(), { vm.set("target_operator_tenant_id", "") }, enabled = enabled); Text("Route by service area") }
     state.operators.forEach { option -> Row { RadioButton(state.fields["target_operator_tenant_id"] == option.id, { vm.set("target_operator_tenant_id", option.id) }, enabled = enabled); Text(option.name) } }
     Text("Preferred times use ${TokenStore.calendarTimezone()}. The operator confirms the booking.")
     Button(onClick = { confirm = "create" to "" }, enabled = enabled && !state.uncertain) { Text("Review and send request") }
     OutlinedButton(onClick = vm::discard, enabled = enabled) { Text("Discard request draft") }
    }
   }
   if(!creating && state.rows.isEmpty() && enabled) item { Text("No booking requests yet") }
   items(state.rows, key = { it.id }) { row -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
    Text("${row.customer} · ${row.status}", style = MaterialTheme.typography.titleMedium)
    Text("${row.shop} → ${row.operator}"); Text(row.address)
    row.schedule?.let { Text("Preferred ${au.mainspring.nativeapp.ui.formatShopDate(it, TokenStore.calendarTimezone())}") }
    row.notes?.let { Text(it) }; row.declineReason?.let { Text("Declined: $it") }; row.conflict?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    if(row.status == "pending") {
     if(row.requestingTenant == tenant) OutlinedButton(onClick = { confirm = "cancel" to row.id }, enabled = enabled) { Text("Cancel request") }
     if(row.targetTenant == tenant) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
      Button(onClick = { confirm = "accept" to row.id }, enabled = enabled) { Text("Accept request") }
      OutlinedButton(onClick = { reason = ""; confirm = "decline" to row.id }, enabled = enabled) { Text("Decline") }
     }
    }
    if(row.targetTenant == tenant) row.jobId?.let { id -> OutlinedButton(onClick = { onOpenJob(id) }) { Text("Open resulting job") } }
   } } }
   if(state.rows.size < state.total) item { OutlinedButton(onClick = vm::loadMore, enabled = enabled) { Text("Load more requests") } }
  }
 }
 confirm?.let { action -> AlertDialog(onDismissRequest = { confirm = null }, title = { Text(when(action.first) { "create" -> "Send booking request?"; "accept" -> "Accept and create job?"; "decline" -> "Decline booking?"; else -> "Cancel booking request?" }) },
  text = { Column { Text(when(action.first) { "create" -> "Send the customer's details and preferred visit time to the selected operator or service-area routing."; "accept" -> "Create a mobile job for this request. Review scheduling warnings after acceptance."; else -> "Update this request's status." })
   if(action.first == "decline") OutlinedTextField(reason, { reason = it }, label = { Text("Reason (optional)") })
  } }, confirmButton = { Button(onClick = { confirm = null; if(action.first == "create") vm.create { creating = false } else vm.action(action.second, action.first, reason) }) { Text("Confirm") } },
  dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancel") } }) }
}
