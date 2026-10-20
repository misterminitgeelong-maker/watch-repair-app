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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun CounterSaleScreen(onBack: () -> Unit,onOpenJob: (String,Boolean) -> Unit,vm: CounterSaleViewModel = viewModel()) {
 val state by vm.state.collectAsStateWithLifecycle(); var confirmation by remember { mutableStateOf<CounterSaleRequest?>(null) }; var localError by remember { mutableStateOf<String?>(null) }
 var confirmReset by remember { mutableStateOf(false) }
 val f = vm::field; val done = f("done") == "true"; val locked = state.busy || f("jobId").isNotBlank() || f("uncertain").isNotBlank()
 BackHandler { if(!state.busy) onBack() }
 Scaffold(containerColor = MaterialTheme.colorScheme.background, topBar = { Column {
    Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 12.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
      TextButton(onClick = onBack, enabled = !state.busy, modifier = Modifier.heightIn(min = 48.dp)) { Text("‹ Jobs", style = MaterialTheme.typography.titleSmall) }
    }
    au.mainspring.nativeapp.ui.LargeHeader(if(au.mainspring.nativeapp.ui.LocalCalibre.current) "POS / Mobile services" else "Mobile services · Sale or quote", "Point of sale", insets = false)
  } }) { padding ->
  Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),verticalArrangement = Arrangement.spacedBy(10.dp)) {
   if(state.busy || state.customerLoading) LinearProgressIndicator(Modifier.fillMaxWidth())
   (localError ?: state.error)?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
   if(done) {
    Text(if(f("mode").ifBlank { "sale" } == "sale") "Sale and unpaid invoice created" else "Draft quote created",style = MaterialTheme.typography.titleLarge)
    Text("Record payment from the invoice after receiving the funds.")
    Button(onClick = { onOpenJob(f("jobId"),f("accountId").isNotBlank()) }) { Text("Open job quotes and invoices") }
    OutlinedButton(onClick = vm::reset) { Text("Start another checkout") }
   } else if(f("request").isNotBlank() && (locked || f("savedCustomerId").isNotBlank())) {
    Text("Checkout saved on this device")
    if(f("jobId").isNotBlank()) OutlinedButton(onClick = { onOpenJob(f("jobId"),f("accountId").isNotBlank()) }) { Text("Review job quotes and invoices") }
    if(f("uncertain").isNotBlank()) {
     OutlinedButton(onClick = vm::review,enabled = !state.busy) { Text("Check existing records") }
     state.recovery.forEach { row -> OutlinedButton(onClick = { vm.useReviewedRecord(row.id) },enabled = !state.busy) { Text("Use saved record: ${row.label}") } }
     OutlinedButton(onClick = vm::confirmNotSaved,enabled = state.reviewed && !state.busy) { Text("I checked: this step was not saved") }
    } else Button(onClick = vm::resume,enabled = !state.busy) { Text("Continue saved checkout") }
    OutlinedButton(onClick = { confirmReset = true }, enabled = !state.busy && (f("uncertain").isBlank() || state.reviewed)) { Text("Discard checkout draft") }
   } else {
    au.mainspring.nativeapp.ui.SegmentedPills(listOf("sale" to "Counter sale","quote" to "Quote only"),f("mode").ifBlank { "sale" },{ if(!locked) vm.set("mode",it) })
    if(au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.MonoLabel("Customer / job",Modifier.padding(top = 6.dp))
    au.mainspring.nativeapp.ui.SegmentedPills(listOf("existing" to "Existing customer","new" to "New customer"),f("customerMode").ifBlank { "existing" },{ if(!locked) vm.set("customerMode",it) })
    if(f("customerMode") == "new") listOf("name" to "Customer name *","phone" to "Phone","email" to "Email").forEach { (key,label) -> au.mainspring.nativeapp.ui.AtelierTextField(f(key),{ vm.set(key,it) },label = { Text(label) },modifier = Modifier.fillMaxWidth(),enabled = !locked) }
    else {
     au.mainspring.nativeapp.ui.AtelierTextField(f("query"),{ vm.set("query",it) },label = { Text("Search customer") },modifier = Modifier.fillMaxWidth(),enabled = !locked)
     OutlinedButton(onClick = { vm.searchCustomers(f("query")) },enabled = !locked && !state.customerLoading) { Text("Search customers") }
     state.customers.forEach { customer -> au.mainspring.nativeapp.ui.SelectableCard(f("customerId") == customer.id,{ vm.set("customerId",customer.id) },enabled = !locked) {
        Text(customer.fullName,style = MaterialTheme.typography.titleMedium)
        customer.phone?.takeIf { it.isNotBlank() }?.let { Text(it,style = MaterialTheme.typography.bodyMedium,color = MaterialTheme.colorScheme.onSurfaceVariant) } } }
     state.accounts.filter { it.active && f("customerId") in it.customerIds }.forEach { account -> au.mainspring.nativeapp.ui.AtelierChip(f("accountId") == account.id,{ vm.set("accountId",if(f("accountId") == account.id) "" else account.id) },enabled = !locked,label = { Text("Account: ${account.name}") }) }
     if(f("customerId").isNotBlank() && state.linkJobs.isNotEmpty()) {
      Text("Link to job (optional)",style = MaterialTheme.typography.labelLarge,modifier = Modifier.padding(top = 4.dp))
      au.mainspring.nativeapp.ui.AtelierChip(f("linkJobId").isBlank(),{ vm.set("linkJobId","") },enabled = !locked,label = { Text("Create new job") },modifier = Modifier.heightIn(min = 48.dp).testTag("pos-link-new"))
      state.linkJobs.forEach { job -> au.mainspring.nativeapp.ui.AtelierChip(f("linkJobId") == job.id,{ vm.set("linkJobId",if(f("linkJobId") == job.id) "" else job.id) },enabled = !locked,
       label = { Text("${job.jobNumber} · ${listOfNotNull(job.vehicleMake,job.vehicleModel).joinToString(" ").ifBlank { job.title }}") },modifier = Modifier.heightIn(min = 48.dp).testTag("pos-link-${job.id}")) }
     }
    }
    if(au.mainspring.nativeapp.ui.LocalCalibre.current) { HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant); au.mainspring.nativeapp.ui.MonoLabel("Cart",Modifier.padding(top = 6.dp)) } else { HorizontalDivider(); Text("Items",style = MaterialTheme.typography.titleLarge) }
    QuoteComposer("quote-composer/pos",f("accountId").isNotBlank(),!locked && TokenStore.canWorkJobs(),catalogue = true,quickSale = true,buttonLabel = if(f("mode").ifBlank { "sale" } == "sale") "Review counter sale" else "Review quote",onSave = { lines,gst,inclusive ->
     try { confirmation = vm.prepare(lines,gst,inclusive); localError = null } catch(e: Exception) { localError = e.userMessage() }
    })
   }
  }
 }
 confirmation?.let { request -> AlertDialog(onDismissRequest = { confirmation = null },title = { Text(if(request.mode == "sale") "Create counter sale?" else "Save quote?") },
  text = { Text(if(request.mode == "sale") "Create the job, quote and unpaid invoice, then mark the work complete. Record payment separately after receiving funds." else "Create the job and draft quote. Review its final totals before sending it to the customer.") },
  confirmButton = { Button(onClick = { confirmation = null; vm.submit(request) }) { Text("Confirm checkout") } },dismissButton = { TextButton(onClick = { confirmation = null }) { Text("Cancel") } }) }
 if(confirmReset) AlertDialog(onDismissRequest = { confirmReset = false }, title = { Text("Discard checkout draft?") }, text = { Text("Any saved customers, jobs, quotes and invoices remain in your shop records. Clear this device's checkout draft and start again.") },
  confirmButton = { Button(onClick = { confirmReset = false; vm.reset() }) { Text("Discard draft") } }, dismissButton = { TextButton(onClick = { confirmReset = false }) { Text("Cancel") } })
}
