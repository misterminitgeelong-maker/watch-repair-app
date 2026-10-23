package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.AccountsViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*

private fun roleLabel(role: String) = when(role) {
    "owner" -> "Owner"; "manager" -> "Manager"; "tech" -> "Technician"; "intake" -> "Clerk"; "platform_admin" -> "Platform admin"
    else -> role.replace('_', ' ').replaceFirstChar { it.uppercase() }
}
private fun humanize(value: String) = value.replace('_', ' ').replaceFirstChar { it.uppercase() }
private fun limit(n: Int) = if(n <= 0 || n >= 1_000_000) "Unlimited" else n.toString()

@Composable fun AccountsScreen(onBack: () -> Unit, onSignOut: () -> Unit, viewModel: AccountsViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var confirmSignOut by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    val session = state.session
    val manager = TokenStore.canManageInvoices()
    Scaffold(topBar = { BackLargeHeader("More", "Account", "Accounts", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            if(state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.error?.let { item { ErrorBanner(it, onRetry = viewModel::refresh) } }
            item {
                SectionLabel("Signed in")
                FlatPanel {
                    DetailRow("Name", session?.user?.fullName.orEmpty())
                    DetailRow("Email", session?.user?.email.orEmpty())
                    DetailRow("Role", session?.user?.role?.let(::roleLabel).orEmpty())
                }
                SectionLabel("Shop")
                FlatPanel {
                    DetailRow("Name", session?.shopName ?: TokenStore.shopValue("name").orEmpty())
                    DetailRow("ABN", session?.shopAbn ?: TokenStore.shopValue("abn").orEmpty())
                    DetailRow("Phone", session?.shopPhone ?: TokenStore.shopValue("phone").orEmpty())
                    DetailRow("Address", session?.shopAddress ?: TokenStore.shopValue("address").orEmpty())
                    DetailRow("Currency", session?.currency ?: TokenStore.shopValue("currency") ?: "AUD")
                    DetailRow("Calendar timezone", session?.calendarTimezone ?: TokenStore.calendarTimezone())
                }
            }
            if(session != null) item {
                SectionLabel("Plan")
                FlatPanel {
                    DetailRow("Plan", humanize(session.planCode))
                    DetailRow("Modules", if(session.enabledFeatures.isEmpty()) "None" else session.enabledFeatures.joinToString(", ") { humanize(it) })
                    if(manager) {
                        state.billing?.let { b ->
                            DetailRow("Team members", "${b.usage.users} of ${limit(b.limits.maxUsers)}")
                            DetailRow("Repair jobs", "${b.usage.repairJobs} of ${limit(b.limits.maxRepairJobs)}")
                            DetailRow("Shoe jobs", "${b.usage.shoeJobs} of ${limit(b.limits.maxShoeJobs)}")
                            DetailRow("Auto key jobs", "${b.usage.autoKeyJobs} of ${limit(b.limits.maxAutoKeyJobs)}")
                            DetailRow("Subscription", if(b.stripeSubscriptionId != null) "Active" else if(b.stripeConfigured) "Not subscribed" else "Not set up")
                            b.xeroConnected?.let { DetailRow("Xero", if(it) "Connected" else "Not connected") }
                        }
                        state.billingError?.let { ErrorBanner(it) }
                        if(TokenStore.canManageTeam()) {
                            if(state.billing?.xeroConnected == false) FinishOnWebRow("Connect Xero", "Xero sign-in happens on the web app.", "accounts", "finish-xero")
                            if(state.billing?.stripeConfigured == true) FinishOnWebRow("Stripe payouts", "Set up or check mobile-service payouts on the web app.", "accounts", "finish-stripe-payouts")
                        }
                        MonoLabel("Change plans and billing from the web app.")
                    }
                }
            }
            item {
                Spacer(Modifier.height(16.dp))
                SecondaryAction({ confirmSignOut = true }, Modifier.fillMaxWidth()) { Text("Sign out") }
            }
            if(session != null && session.user.role == "owner") item {
                Spacer(Modifier.height(24.dp))
                SectionLabel("Delete account or shop")
                FlatPanel {
                    Text("Ask Mainspring to delete your login, or the whole shop and its data. Only the shop owner can do this.", style = MaterialTheme.typography.bodySmall)
                    TextButton({ confirmDelete = true }, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Delete account or shop") }
                }
            }
        }
    }
    if(confirmDelete && session != null && session.user.role == "owner")
        AccountDeletionDialog(session.shopName, session.tenantSlug, session.user.email) { confirmDelete = false }
    if(confirmSignOut) AlertDialog(onDismissRequest = { confirmSignOut = false }, title = { Text("Sign out?") },
        text = { Text("Saved drafts remain tied to this shop and account on this device.") },
        confirmButton = { TextButton({ confirmSignOut = false; onSignOut() }) { Text("Sign out") } },
        dismissButton = { TextButton({ confirmSignOut = false }) { Text("Cancel") } })
}
