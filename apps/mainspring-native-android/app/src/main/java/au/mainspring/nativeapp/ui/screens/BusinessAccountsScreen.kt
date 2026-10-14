package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.screens.LinkAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.ui.RefreshOnResume
import au.mainspring.nativeapp.ui.formatCents

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BusinessAccountsScreen(onBack: () -> Unit, onOpenAccount: (String) -> Unit, vm: BusinessAccountsViewModel = viewModel(), onCreate: () -> Unit = {}) {
    val state by vm.state.collectAsStateWithLifecycle()
    var search by rememberSaveable { mutableStateOf("") }
    RefreshOnResume(vm::refresh)
    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Business accounts") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
                androidx.compose.material3.TextButton(onClick = vm::refresh, enabled = !state.loading) { Text("Refresh") }
                if(TokenStore.canManageInvoices()) Button(onClick = onCreate, modifier = if(au.mainspring.nativeapp.ui.LocalCalibre.current) Modifier.fillMaxWidth().heightIn(min = 52.dp) else Modifier) { Text("New business account") }
                au.mainspring.nativeapp.ui.AtelierTextField(search, { search = it }, label = { Text("Find an account") }, modifier = Modifier.fillMaxWidth())
                if(!state.loading && state.accounts.isEmpty() && state.error == null) Text("No business accounts yet.")
            }
            items(state.accounts.filter { "${it.name} ${it.code.orEmpty()}".contains(search, true) }, key = { it.id }) { account ->
                CardOrFlat(onClick = { onOpenAccount(account.id) }, padding = 16.dp, spacing = 0.dp) {
                    Text(account.name, style = MaterialTheme.typography.titleMedium)
                    Text("${if(account.active) "Active" else "Inactive"} · ${account.customerIds.size} linked customers")
                    account.code?.let { Text(it) }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BusinessAccountScreen(accountId: String, onBack: () -> Unit, onOpenCustomer: (String) -> Unit, onOpenJob: (String, String) -> Unit,
    vm: BusinessAccountViewModel = viewModel(key = accountId, factory = BusinessAccountViewModel.factory(accountId)), onEdit: () -> Unit = {}) {
    val state by vm.state.collectAsStateWithLifecycle()
    var confirmInvoice by remember { mutableStateOf(false) }
    val context = androidx.compose.ui.platform.LocalContext.current
    var printError by remember { mutableStateOf<String?>(null) }
    var memberAction by remember { mutableStateOf<Pair<String, Boolean>?>(null) }
    var search by rememberSaveable { mutableStateOf("") }
    val manager = TokenStore.canManageInvoices()
    val enabled = !state.loading && !state.busy
    RefreshOnResume(vm::refresh)
    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text(state.account?.name ?: "Business account") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize().imePadding(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            item {
                if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }; state.info?.let { Text(it) }
                printError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
                androidx.compose.material3.TextButton(onClick = vm::refresh, enabled = enabled) { Text("Refresh") }
                if(manager) OutlinedButton(onClick = onEdit, enabled = enabled) { Text("Edit account details") }
                state.account?.let { account ->
                    Text("${if(account.active) "Active" else "Inactive"} · ${account.terms} day payment terms")
                    listOfNotNull(account.code, account.contactName, account.phone, account.email, account.address, account.type, account.billingCycle, account.notes).filter { it.isNotBlank() }.forEach { Text(it) }
                    account.fleetSize?.let { Text("Fleet size: $it") }
                }
                Text("Linked customers", style = MaterialTheme.typography.titleLarge)
            }
            items(state.account?.customerIds.orEmpty(), key = { "member/$it" }) { id ->
                val name = state.members.firstOrNull { it.id == id }?.fullName ?: "Open linked customer"
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton(onClick = { onOpenCustomer(id) }, modifier = Modifier.weight(1f)) { Text(name) }
                    if(manager) TextButton(onClick = { memberAction = id to false }, enabled = enabled) { Text("Remove") }
                }
            }
            if(manager) {
                item {
                    au.mainspring.nativeapp.ui.AtelierTextField(search, { search = it }, label = { Text("Customer name, email or phone") }, modifier = Modifier.fillMaxWidth(), enabled = enabled)
                    OutlinedButton(onClick = { vm.searchCustomers(search) }, enabled = enabled && !state.searching) { Text("Search customers") }
                    if(state.searching) LinearProgressIndicator(Modifier.fillMaxWidth())
                    if(state.customers.size == 30) Text("Showing 30 matches. Refine your search to find another customer.")
                }
                items(state.customers.filter { it.id !in state.account?.customerIds.orEmpty() }, key = { "candidate/${it.id}" }) { customer ->
                    OutlinedButton(onClick = { memberAction = customer.id to true }, enabled = enabled, modifier = Modifier.fillMaxWidth()) { Text("Link ${customer.fullName}") }
                }
            }
            item {
                HorizontalDivider(); Text("Monthly statement", style = MaterialTheme.typography.titleLarge)
                Text("The statement includes completed billable jobs that have not already been invoiced to this account.")
                au.mainspring.nativeapp.ui.AtelierTextField(state.period, vm::setPeriod, label = { Text("Billing month MM/YYYY") }, enabled = enabled && !state.uncertain, modifier = Modifier.fillMaxWidth())
                OutlinedButton(onClick = vm::preview, enabled = enabled) { Text("Preview statement") }
                if(state.uncertain) {
                    Text("The last invoice result is unknown. Refresh and review the invoices before repeating it.")
                    OutlinedButton(onClick = vm::checkedHistory, enabled = enabled && state.historyChecked) { Text("I have reviewed the account invoices") }
                }
            }
            state.statement?.let { statement ->
                items(statement.lines, key = { "statement/${it.sourceType}/${it.jobId}" }) { line ->
                    TextButton(onClick = { onOpenJob(line.sourceType, line.jobId) }) { Text("${line.jobNumber} · ${line.description} · ${formatCents(line.amount, "AUD")}") }
                }
                item {
                    Text("Statement subtotal ${formatCents(statement.subtotal, "AUD")}")
                    if(manager) {
                        au.mainspring.nativeapp.ui.AtelierTextField(state.tax, vm::setTax, label = { Text("GST amount (AUD)") }, enabled = enabled, modifier = Modifier.fillMaxWidth())
                        Button(onClick = { confirmInvoice = true }, enabled = enabled && !state.uncertain && statement.lines.isNotEmpty() && state.invoices.none { it.year == statement.year && it.month == statement.month }) { Text("Generate monthly invoice") }
                    }
                }
            }
            item { HorizontalDivider(); Text("Account invoices", style = MaterialTheme.typography.titleLarge)
                if(enabled && state.invoices.isEmpty()) Text("No account invoices saved.") }
            items(state.invoices, key = { it.id }) { invoice ->
                CardOrFlat { Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("${invoice.number} · ${invoice.month}/${invoice.year}", style = MaterialTheme.typography.titleMedium)
                    Text("${invoice.status} · ${formatCents(invoice.total, invoice.currency)}")
                    Text("Subtotal ${formatCents(invoice.subtotal, invoice.currency)} · GST ${formatCents(invoice.tax, invoice.currency)}")
                    OutlinedButton(onClick = { try {
                        printInvoiceSummary(context,InvoiceSummary(invoice.number,invoice.status,
                            details = listOf("Account: ${state.account?.name.orEmpty()}","Billing period: ${invoice.month}/${invoice.year}"),
                            items = invoice.lines.map { "${it.jobNumber} · ${it.description} · ${formatCents(it.amount,invoice.currency)}" },
                            totals = listOf("Subtotal" to formatCents(invoice.subtotal,invoice.currency),"Tax / GST" to formatCents(invoice.tax,invoice.currency),"Total" to formatCents(invoice.total,invoice.currency))))
                    } catch(e: Exception) { printError = e.userMessage() } },enabled = enabled) { Text("Print / save invoice summary") }
                    invoice.lines.forEach { line -> TextButton(onClick = { onOpenJob(line.sourceType, line.jobId) }) { Text("${line.jobNumber} · ${line.description} · ${formatCents(line.amount, invoice.currency)}") } }
                } }
            }
        }
    }
    if(confirmInvoice) AlertDialog(onDismissRequest = { confirmInvoice = false }, title = { Text("Generate monthly invoice?") },
        text = { Text("Create the account invoice for ${state.period} with GST of AUD ${state.tax}. The server calculates the final billable total.") },
        confirmButton = { TextButton(onClick = { confirmInvoice = false; vm.generate() }) { Text("Confirm invoice") } },
        dismissButton = { TextButton(onClick = { confirmInvoice = false }) { Text("Cancel") } })
    memberAction?.let { action -> AlertDialog(onDismissRequest = { memberAction = null }, title = { Text(if(action.second) "Link customer?" else "Remove customer from account?") },
        text = { Text(if(action.second) "Link this customer to ${state.account?.name}." else "Remove account membership. The customer's existing jobs remain saved.") },
        confirmButton = { TextButton(onClick = { memberAction = null; vm.member(action.first, action.second) }) { Text("Confirm membership change") } },
        dismissButton = { TextButton(onClick = { memberAction = null }) { Text("Cancel") } }) }
}
