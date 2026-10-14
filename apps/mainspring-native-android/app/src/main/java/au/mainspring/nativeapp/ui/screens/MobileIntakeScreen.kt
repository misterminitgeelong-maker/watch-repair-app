package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SelectableCard
import au.mainspring.nativeapp.ui.ErrorBanner
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.horizontalScroll
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
import au.mainspring.nativeapp.ui.SectionLabel

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable fun MobileIntakeScreen(onBack: () -> Unit,onOpenJob: (String) -> Unit,vm: MobileIntakeViewModel = viewModel(),preselectedCustomerId: String? = null, onSwitchService: ((String) -> Unit)? = null, services: List<Pair<String, String>> = emptyList()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val locked = state.busy || vm.field("uncertain").isNotBlank() || vm.field("jobId").isNotBlank() || vm.field("hasAcknowledgement") == "true"
    var leave by remember {mutableStateOf(false)};var discard by remember {mutableStateOf(false)};var reconcile by remember {mutableStateOf(false)}
    BackHandler {if(!state.busy) leave=true}
    LaunchedEffect(Unit) {if(preselectedCustomerId!=null && state.fields.isEmpty()) {vm.set("customerId",preselectedCustomerId);vm.set("customerMode","existing")};vm.search()}
    Scaffold(topBar = { au.mainspring.nativeapp.ui.IntakeHeader("auto_key", { leave = true }, !state.busy, { discard = true }, !state.busy && vm.field("uncertain").isBlank() && vm.field("jobId").isBlank(), services, onSwitchService) },
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar={if(vm.field("jobId").isBlank()) Surface(color=MaterialTheme.colorScheme.surface) {Column {if(au.mainspring.nativeapp.ui.LocalCalibre.current) HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant);Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(12.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            OutlinedButton({leave=true},enabled=!state.busy,modifier=Modifier.weight(1f)) {Text("Cancel")}
            Button(vm::submit,enabled=!state.busy && vm.field("uncertain").isBlank() && TokenStore.canWorkJobs(),modifier=Modifier.weight(1f)) {Text("Create job")}
        } } } }) {padding ->
        Column(Modifier.fillMaxSize().padding(padding).imePadding().verticalScroll(rememberScrollState()).padding(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
            if(au.mainspring.nativeapp.ui.LocalCalibre.current) {
                au.mainspring.nativeapp.ui.MonoLabel("Mobile intake / draft saved on this device")
                Text("Start a mobile job",style=MaterialTheme.typography.headlineMedium)
                HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
            } else Text("Draft saved on this device",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            state.error?.let {ErrorBanner(it)}
            vm.field("trackingWarning").takeIf(String::isNotBlank)?.let {ErrorBanner(it)}
            if(state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if(vm.field("uncertain").isNotBlank()) OutlinedButton({reconcile=true}) {Text("I checked shop records")}
            if(vm.field("jobId").isNotBlank()) Button({val id=vm.field("jobId");vm.finish();onOpenJob(id)}) {Text("Job saved · open job")}
            @Composable fun field(key: String,label: String,modifier: Modifier=Modifier.fillMaxWidth()) {
                au.mainspring.nativeapp.ui.AtelierTextField(vm.field(key),{vm.set(key,it)},label={Text(label)},modifier=modifier,enabled=!locked)
            }
            SectionLabel("Job type")
            FlowRow(horizontalArrangement=Arrangement.spacedBy(6.dp)) {
                listOf("Key Cutting (in-store)","Lockout \u2013 Car","Lockout \u2013 Boot/Trunk","Lockout \u2013 Roadside","All Keys Lost","Duplicate Key","Transponder Programming","Remote / Fob Sync","Ignition Repair","Ignition Replace","Broken Key Extraction","Door Lock Change","Diagnostic").forEach {type ->
                    au.mainspring.nativeapp.ui.AtelierChip(vm.field("jobType")==type,{
                        val old=vm.field("jobType");vm.set("jobType",type)
                        if(vm.field("title").isBlank() || vm.field("title")==old) vm.set("title",type)
                    },enabled=!locked,label={Text(type)})
                }
            }
            field("title","Job title *")
            SectionLabel("Customer")
                    val new = vm.field("customerMode") == "new"
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        au.mainspring.nativeapp.ui.AtelierChip(selected = !new, onClick = { vm.set("customerMode", "existing") }, enabled = !locked, label = { Text("Existing") })
                        au.mainspring.nativeapp.ui.AtelierChip(selected = new, onClick = { vm.set("customerMode", "new"); vm.set("customerId", "") }, enabled = !locked, label = { Text("New customer") })
                    }
                    if(new) { field("name", "Name *"); field("phone", "Phone"); field("email", "Email") }
                    else {
                        au.mainspring.nativeapp.ui.AtelierTextField(vm.field("query"), { vm.set("query", it) }, label = { Text("Search customers") }, singleLine = true, enabled = !locked, modifier = Modifier.fillMaxWidth(),
                            keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Search),
                            keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSearch = { vm.search() }))
                        state.customers.forEach { c ->
                            SelectableCard(selected = vm.field("customerId") == c.id, onClick = { vm.set("customerId", c.id) }, enabled = !locked) {
                                Text(c.fullName, style = MaterialTheme.typography.titleMedium)
                                c.phone?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                            }
                        }
                        if(state.accountsLoading) LinearProgressIndicator(Modifier.fillMaxWidth())
                        state.accountError?.let { ErrorBanner(it) }
                        val accounts = state.accounts.filter { it.active && vm.field("customerId") in it.customerIds }
                        if(accounts.isNotEmpty() || vm.field("accountId").isNotBlank()) {
                            Text("Billing account (optional)")
                            au.mainspring.nativeapp.ui.AtelierChip(vm.field("accountId").isBlank(),{ vm.set("accountId","") },enabled = !locked,label = { Text("No account") })
                            accounts.forEach { account -> au.mainspring.nativeapp.ui.AtelierChip(vm.field("accountId") == account.id,{ vm.set("accountId",account.id) },enabled = !locked,label = { Text(account.name) }) }
                        }
                    }
            SectionLabel("Vehicle")
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {field("make","Make",Modifier.weight(1f));field("model","Model",Modifier.weight(1f))}
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {field("year","Year",Modifier.weight(1f));field("plate","Registration",Modifier.weight(1f))}
            field("vin","VIN")
            SectionLabel("Location and booking")
            field("address","Job address")
            field("scheduled","Booking (DD/MM/YYYY HH:mm)")
            Text("Times use ${TokenStore.calendarTimezone()}",style=MaterialTheme.typography.bodySmall)
            Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                au.mainspring.nativeapp.ui.AtelierChip(vm.field("technician").isBlank(),{vm.set("technician","")},enabled=!locked,label={Text("Unassigned")})
                state.technicians.filter {it.active && it.role in listOf("tech","manager","owner")}.forEach {user->au.mainspring.nativeapp.ui.AtelierChip(vm.field("technician")==user.id,{vm.set("technician",user.id)},enabled=!locked,label={Text(user.name)})}
            }
            SectionLabel("Priority")
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {listOf("low","normal","high","urgent").forEach {value->au.mainspring.nativeapp.ui.AtelierChip(vm.field("priority").ifBlank {"normal"}==value,{vm.set("priority",value)},enabled=!locked,label={Text(value.replaceFirstChar {it.uppercase()})})}}
            SectionLabel("Work details")
            field("description","Requested work");field("keyType","Key type");field("quantity","Key quantity (default 1)");field("notes","Technician notes");field("deposit","Deposit ($)")
            SectionLabel("Initial status")
            Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(8.dp)) {listOf("awaiting_quote","go_ahead","pending_booking","booked").forEach {value->au.mainspring.nativeapp.ui.AtelierChip(vm.field("status").ifBlank {"awaiting_quote"}==value,{vm.set("status",value)},enabled=!locked,label={Text(au.mainspring.nativeapp.ui.statusLabel(value))})}}
            Row(verticalAlignment=androidx.compose.ui.Alignment.CenterVertically) {Checkbox(vm.field("bookingSms")=="true",{vm.set("bookingSms",it.toString())},enabled=!locked);Text("Send booking SMS to customer")}
            Text("Creation may also send the customer's tracking message according to shop settings.",style=MaterialTheme.typography.bodySmall)
        }
    }
    if(leave) AlertDialog(onDismissRequest = { leave = false }, title = { Text("Leave intake?") }, text = { Text("Your draft stays on this device.") },
        confirmButton = { TextButton(onClick = onBack) { Text("Save and leave") } }, dismissButton = { TextButton(onClick = { leave = false }) { Text("Keep editing") } })
    if(discard) AlertDialog(onDismissRequest = { discard = false }, title = { Text("Discard draft?") }, text = { Text("Clear device details without deleting any shop records.") },
        confirmButton = { TextButton(onClick = { vm.discard(); discard = false }) { Text("Discard") } }, dismissButton = { TextButton(onClick = { discard = false }) { Text("Cancel") } })
    if(reconcile) AlertDialog(onDismissRequest = { reconcile = false }, title = { Text("Confirm no record saved") }, text = { Text("Only allow a retry after checking that the last attempted customer/job does not exist. Retrying an existing save can duplicate it.") },
        confirmButton = { TextButton(onClick = { vm.set("uncertain", ""); reconcile = false }) { Text("Not saved — allow retry") } }, dismissButton = { TextButton(onClick = { reconcile = false }) { Text("Cancel") } })
}
