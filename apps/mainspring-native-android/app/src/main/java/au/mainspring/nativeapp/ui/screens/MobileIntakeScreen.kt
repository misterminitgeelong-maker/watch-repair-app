package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.consumeWindowInsets
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
import au.mainspring.nativeapp.ui.FlatPanel
import au.mainspring.nativeapp.ui.formatCents
import androidx.compose.ui.platform.testTag

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable fun MobileIntakeScreen(onBack: () -> Unit,onOpenJob: (String) -> Unit,vm: MobileIntakeViewModel = viewModel(),preselectedCustomerId: String? = null, onSwitchService: ((String) -> Unit)? = null, services: List<Pair<String, String>> = emptyList()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val locked = state.busy || vm.field("uncertain").isNotBlank() || vm.field("jobId").isNotBlank() || vm.field("hasAcknowledgement") == "true"
    var leave by remember {mutableStateOf(false)};var discard by remember {mutableStateOf(false)};var reconcile by remember {mutableStateOf(false)}
    var pricingOpen by remember { mutableStateOf(false) }
    BackHandler {if(!state.busy) leave=true}
    LaunchedEffect(Unit) {if(preselectedCustomerId!=null && state.fields.isEmpty()) {vm.set("customerId",preselectedCustomerId);vm.set("customerMode","existing")};vm.search()}
    Scaffold(topBar = { au.mainspring.nativeapp.ui.IntakeHeader("auto_key", { leave = true }, !state.busy, { discard = true }, !state.busy && vm.field("uncertain").isBlank() && vm.field("jobId").isBlank(), services, onSwitchService) },
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar={if(vm.field("jobId").isBlank() && au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.WizardActionRow("Cancel",{leave=true},!state.busy,"Create job",vm::submit,!state.busy && vm.field("uncertain").isBlank() && TokenStore.canWorkJobs())
        else if(vm.field("jobId").isBlank()) Surface(color=MaterialTheme.colorScheme.surface) {Column {if(au.mainspring.nativeapp.ui.LocalCalibre.current) HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant);Row(Modifier.fillMaxWidth().navigationBarsPadding().imePadding().padding(12.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            OutlinedButton({leave=true},enabled=!state.busy,modifier=Modifier.weight(1f)) {Text("Cancel")}
            Button(vm::submit,enabled=!state.busy && vm.field("uncertain").isBlank() && TokenStore.canWorkJobs(),modifier=Modifier.weight(1f)) {Text("Create job")}
        } } } }) {padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding().verticalScroll(rememberScrollState()).padding(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
            if(!au.mainspring.nativeapp.ui.LocalCalibre.current) Text("Draft saved on this device",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            state.error?.let {ErrorBanner(it)}
            vm.field("trackingWarning").takeIf(String::isNotBlank)?.let {ErrorBanner(it)}
            if(state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if(vm.field("uncertain").isNotBlank()) OutlinedButton({reconcile=true}) {Text("I checked shop records")}
            if(vm.field("jobId").isNotBlank()) Button({val id=vm.field("jobId");vm.finish();onOpenJob(id)}) {Text("Job saved · open job")}
            @Composable fun field(key: String,label: String,modifier: Modifier=Modifier.fillMaxWidth()) {
                au.mainspring.nativeapp.ui.WizardField(label,vm.field(key),{vm.set(key,it)},modifier=modifier,enabled=!locked,placeholder=when(key) {"name"->"Jane Smith";"phone"->"0412 345 678";"email"->"jane@example.com";else->null})
            }
            SectionLabel("Job type")
            val currentType = vm.field("jobType")
            val jobTypes = (MOBILE_JOB_TYPES + listOfNotNull(currentType.takeIf { it.isNotBlank() })).distinct()
            WebSelect(currentType.ifBlank { "Choose job type" }, listOf("" to "No preset") + jobTypes.map { it to it }, { type ->
                val old=vm.field("jobType");vm.set("jobType",type)
                if(vm.field("title").isBlank() || vm.field("title")==old) vm.set("title",type)
            }, tag="intake-job-type", description="Job type", enabled=!locked)
            SectionLabel("Additional services (optional)")
            val extras = vm.extras()
            extras.forEachIndexed {idx,row ->
                FlatPanel(Modifier.testTag("intake-extra-$idx")) {
                    WebSelect(row.preset.ifBlank { "Choose service or enter a custom note" },
                        listOf("" to "Custom note only") + (MOBILE_JOB_TYPES + listOfNotNull(row.preset.takeIf { it.isNotBlank() })).distinct().map { it to it },
                        { type -> vm.setExtras(extras.toMutableList().also { it[idx]=row.copy(preset=type) }) },
                        tag="intake-extra-type-$idx", description="Additional service ${idx+1}", enabled=!locked)
                    au.mainspring.nativeapp.ui.WizardField("Or custom note",row.custom,{text -> vm.setExtras(extras.toMutableList().also {it[idx]=row.copy(custom=text)})},modifier=Modifier.fillMaxWidth().testTag("intake-extra-$idx-custom"),enabled=!locked,placeholder="Custom work\u2026")
                    TextButton({vm.setExtras(extras.filterIndexed {i,_ -> i!=idx})},enabled=!locked,modifier=Modifier.heightIn(min=48.dp).testTag("intake-extra-$idx-remove")) {Text("Remove line")}
                }
            }
            OutlinedButton({vm.setExtras(extras+ExtraService())},enabled=!locked,modifier=Modifier.testTag("intake-extra-add")) {Text("Add another service line")}
            field("title","Job Title *")
            SectionLabel("Customer")
                    val new = vm.field("customerMode") == "new"
                    au.mainspring.nativeapp.ui.CustomerModeToggle(new, { vm.set("customerMode", "existing") }, { vm.set("customerMode", "new"); vm.set("customerId", "") }, !locked)
                    if(new) { field("name", "Full Name *"); field("phone", "Phone"); field("email", "Email") }
                    else {
                        au.mainspring.nativeapp.ui.WizardField("Search Customer", vm.field("query"), { vm.set("query", it) }, placeholder = "Type name, phone or email...", singleLine = true, enabled = !locked, modifier = Modifier.fillMaxWidth(),
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
                            au.mainspring.nativeapp.ui.FilterDropdown("Billing account",listOf<Pair<String?,String>>("" to "No account")+accounts.map { it.id to it.name },vm.field("accountId"),{ if(!locked) vm.set("accountId",it ?: "") },Modifier.testTag("intake-account"))
                        }
                    }
            if(vm.showLastVehicle()) state.lastJob?.let {job ->
                FlatPanel(Modifier.testTag("intake-last-vehicle")) {
                    Text("LAST VISIT VEHICLE ON FILE",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.primary)
                    Text(lastVehicleSummary(job),style=MaterialTheme.typography.bodyMedium)
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                        OutlinedButton({vm.dismissLastVehicle()},enabled=!locked,modifier=Modifier.testTag("intake-last-vehicle-skip")) {Text("Skip")}
                        Button({vm.applyLastVehicle()},enabled=!locked,modifier=Modifier.testTag("intake-last-vehicle-use")) {Text("Use this")}
                    }
                }
            }
            SectionLabel("Vehicle")
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {field("make","Make",Modifier.weight(1f));field("model","Model",Modifier.weight(1f))}
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {field("year","Year",Modifier.weight(1f));field("plate","Registration",Modifier.weight(1f))}
            if(state.specMatches.isNotEmpty()) {
                Text("KEY DATABASE MATCHES \u00b7 TAP TO FILL",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                state.specMatches.take(5).forEachIndexed {i,m ->
                    SelectableCard(selected=false,onClick={vm.applySpec(m)},modifier=Modifier.testTag("intake-spec-match-$i"),enabled=!locked) {
                        Text(m.label.ifBlank {"${m.vehicleMake} ${m.vehicleModel}"},style=MaterialTheme.typography.titleSmall)
                        specMatchSummary(m).takeIf(String::isNotBlank)?.let {Text(it,style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                        specBlanks(m).takeIf(String::isNotBlank)?.let {Text("Blanks: $it",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                    }
                }
            }
            field("vin","VIN")
            Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {field("blade","Blade / blank ref.",Modifier.weight(1f));field("chip","Chip / transponder",Modifier.weight(1f))}
            SectionLabel("Location and booking")
            field("address","Job address")
            state.addressSuggestions.forEachIndexed {i,address -> SelectableCard(selected=false,onClick={vm.pickAddress(address)},modifier=Modifier.testTag("intake-address-suggestion-$i"),enabled=!locked) {Text(address,style=MaterialTheme.typography.bodyMedium)}}
            field("scheduled","Booking (DD/MM/YYYY HH:mm)")
            Text("Times use ${TokenStore.calendarTimezone()}",style=MaterialTheme.typography.bodySmall)
            au.mainspring.nativeapp.ui.FilterDropdown("Technician",listOf<Pair<String?,String>>("" to "Unassigned")+state.technicians.filter {it.active && it.role in listOf("tech","manager","owner")}.map {it.id to it.name},vm.field("technician"),{ if(!locked) vm.set("technician",it ?: "") },Modifier.testTag("intake-technician"))
            SectionLabel("Job source (commission tier)")
            au.mainspring.nativeapp.ui.FilterDropdown("Job source",MOBILE_COMMISSION_SOURCES.map {(value,label)->value to label},vm.field("commission").ifBlank {DEFAULT_COMMISSION_SOURCE},{ if(!locked && it != null) vm.set("commission",it) },Modifier.testTag("intake-commission"))
            field("salesperson","Salesperson")
            SectionLabel("Priority")
            au.mainspring.nativeapp.ui.FilterDropdown("Priority",listOf("low","normal","high","urgent").map {it to it.replaceFirstChar {c->c.uppercase()}},vm.field("priority").ifBlank {"normal"},{ if(!locked && it != null) vm.set("priority",it) },Modifier.testTag("intake-priority"))
            SectionLabel("Work details")
            field("description","Requested work");field("keyType","Key type");field("quantity","Key quantity (default 1)");field("notes","Technician notes");field("deposit","Deposit ($)")
            SectionLabel("Suggested quote")
            FlatPanel(Modifier.testTag("intake-suggested-quote")) {
                val currency = TokenStore.shopValue("currency")?.takeIf(String::isNotBlank) ?: "AUD"
                val quote = state.suggestion
                if(quote == null) LinearProgressIndicator(Modifier.fillMaxWidth()) else {
                    quote.lines.forEach {line -> Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                        Text(if(line.quantity>1) "${line.description} \u00d7 ${line.quantity.toInt()}" else line.description,Modifier.weight(1f),style=MaterialTheme.typography.bodyMedium)
                        Text(formatCents(line.totalPriceCents,currency),style=MaterialTheme.typography.bodyMedium)
                    } }
                    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {Text("Total incl. GST (${quote.tier} pricing)",Modifier.weight(1f),style=MaterialTheme.typography.titleSmall);Text(formatCents(quote.totalCents,currency),Modifier.testTag("intake-suggested-total"),style=MaterialTheme.typography.titleSmall)}
                    if(quote.estimated) Text("Estimate only: shop pricing could not be loaded. The shop's own prices are applied when the job is created.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            au.mainspring.nativeapp.ui.LabeledCheckbox(vm.field("applyQuote")!="false",vm::applySuggested,modifier=Modifier.testTag("intake-apply-quote"),enabled=!locked) {Text("Apply suggested quote to this job")}
            OutlinedTextField(vm.field("manualPrice"), vm::manualPrice, label = { Text("Customer price ($, including GST)") }, enabled = !locked, modifier = Modifier.fillMaxWidth().testTag("intake-manual-price"))
            vm.field("pricingLabel").takeIf(String::isNotBlank)?.let { Text("Catalogue: $it${if(vm.field("callout") == "true") " · Callout included" else " · Plus callout"}") }
            OutlinedButton({ pricingOpen = true }, enabled = !locked) { Text("Browse pricing catalogue") }
            SectionLabel("Initial status")
            au.mainspring.nativeapp.ui.FilterDropdown("Initial status",listOf("awaiting_quote","go_ahead","pending_booking","booked").map {it to au.mainspring.nativeapp.ui.statusLabel(it)},vm.field("status").ifBlank {"awaiting_quote"},{ if(!locked && it != null) vm.set("status",it) },Modifier.testTag("intake-status"))
            au.mainspring.nativeapp.ui.LabeledCheckbox(vm.field("bookingSms")=="true",{vm.set("bookingSms",it.toString())},enabled=!locked) {Text("Send booking SMS to customer")}
            Text("Creation may also send the customer's tracking message according to shop settings.",style=MaterialTheme.typography.bodySmall)
        }
    }
    if(pricingOpen) MobileIntakePricingDialog({ pricingOpen = false }, { row, category, price -> vm.selectPricing(row, category, price); pricingOpen = false })
    if(leave) AlertDialog(onDismissRequest = { leave = false }, title = { Text("Leave intake?") }, text = { Text("Your draft stays on this device.") },
        confirmButton = { TextButton(onClick = onBack) { Text("Save and leave") } }, dismissButton = { TextButton(onClick = { leave = false }) { Text("Keep editing") } })
    if(discard) AlertDialog(onDismissRequest = { discard = false }, title = { Text("Discard draft?") }, text = { Text("Clear device details without deleting any shop records.") },
        confirmButton = { TextButton(onClick = { vm.discard(); discard = false }) { Text("Discard") } }, dismissButton = { TextButton(onClick = { discard = false }) { Text("Cancel") } })
    if(reconcile) AlertDialog(onDismissRequest = { reconcile = false }, title = { Text("Confirm no record saved") }, text = { Text("Only allow a retry after checking that the last attempted customer/job does not exist. Retrying an existing save can duplicate it.") },
        confirmButton = { TextButton(onClick = { vm.set("uncertain", ""); reconcile = false }) { Text("Not saved — allow retry") } }, dismissButton = { TextButton(onClick = { reconcile = false }) { Text("Cancel") } })
}
