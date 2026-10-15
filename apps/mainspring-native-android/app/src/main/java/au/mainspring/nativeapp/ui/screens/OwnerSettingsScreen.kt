package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.OwnerSettingsViewModel
import au.mainspring.nativeapp.api.ShopIdentity
import au.mainspring.nativeapp.ui.*

/** Shop details (manager+), email alert preferences and integration health. Not yet linked from the shell. */
@Composable fun OwnerSettingsScreen(onBack: () -> Unit, viewModel: OwnerSettingsViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Scaffold(topBar = { BackLargeHeader("More", "Shop", "Shop settings", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("owner-settings"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if(state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            if(state.allowed) {
                item { SectionLabel("Shop details") }
                state.identity?.let { identity -> item(key = "identity-${identity.hashCode()}") { IdentityForm(identity, state.savingIdentity, viewModel) } }
                state.identityInfo?.let { item { Text(it, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.testTag("identity-info")) } }
                state.identityError?.let { item { ErrorBanner(it, modifier = Modifier.testTag("identity-error")) } }
            }
            item { SectionLabel("Email alerts for me") }
            state.prefs?.let { p ->
                item {
                    FlatPanel {
                        PrefRow("Quote approved", "email_quote_approved", p.quoteApproved, state.savingPref, viewModel)
                        PrefRow("Invoice paid", "email_invoice_paid", p.invoicePaid, state.savingPref, viewModel)
                        PrefRow("Customer SMS reply", "email_sms_reply", p.smsReply, state.savingPref, viewModel)
                        PrefRow("Daily digest", "email_daily_digest", p.dailyDigest, state.savingPref, viewModel)
                        PrefRow("Weekly sales report", "email_weekly_sales_report", p.weeklySales, state.savingPref, viewModel)
                        PrefRow("Monthly sales report", "email_monthly_sales_report", p.monthlySales, state.savingPref, viewModel)
                    }
                }
            }
            state.prefsError?.let { item { ErrorBanner(it, onRetry = viewModel::refresh) } }
            item { SectionLabel("Integration health") }
            state.health?.let { h ->
                item {
                    FlatPanel {
                        DetailRow("SMS (Twilio)", if(h.twilioConfigured) "Configured" else "Not configured")
                        h.lastSmsSentAt?.let { DetailRow("Last SMS sent", it.take(16).replace('T', ' ')) }
                        h.lastSmsFailedAt?.let { DetailRow("Last SMS failure", it.take(16).replace('T', ' ')) }
                        DetailRow("Card payments (Stripe)", if(h.stripeConfigured) "Configured" else "Not configured")
                        h.stripeConnectReady?.let { DetailRow("Payouts", if(it) "Ready" else "Finish setup on the web") }
                        DetailRow("Email (SendGrid)", if(h.sendgridConfigured) "Configured" else "Not configured")
                        DetailRow("Photo storage", h.attachmentBackend.ifBlank { "Unknown" })
                    }
                }
            }
            state.healthError?.let { item { ErrorBanner(it, onRetry = viewModel::refresh) } }
        }
    }
}

@Composable private fun PrefRow(label: String, field: String, value: Boolean, saving: String?, viewModel: OwnerSettingsViewModel) {
    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Switch(value, { viewModel.setPref(field, it) }, enabled = saving == null, modifier = Modifier.testTag("pref-$field"))
    }
}

@Composable private fun IdentityForm(identity: ShopIdentity, saving: Boolean, viewModel: OwnerSettingsViewModel) {
    var abn by remember { mutableStateOf(identity.abn.orEmpty()) }
    var phone by remember { mutableStateOf(identity.shopPhone.orEmpty()) }
    var email by remember { mutableStateOf(identity.shopEmail.orEmpty()) }
    var payment by remember { mutableStateOf(identity.paymentInstructions.orEmpty()) }
    var logo by remember { mutableStateOf(identity.logoUrl.orEmpty()) }
    var color by remember { mutableStateOf(identity.brandColor.orEmpty()) }
    FlatPanel {
        DetailRow("Shop", identity.name)
        AtelierTextField(abn, { abn = it.take(20) }, enabled = !saving, singleLine = true, label = { Text("ABN") }, modifier = Modifier.fillMaxWidth().testTag("identity-abn"))
        AtelierTextField(phone, { phone = it.take(40) }, enabled = !saving, singleLine = true, label = { Text("Shop phone") }, modifier = Modifier.fillMaxWidth().testTag("identity-phone"))
        AtelierTextField(email, { email = it.take(200) }, enabled = !saving, singleLine = true, label = { Text("Shop email") }, modifier = Modifier.fillMaxWidth().testTag("identity-email"))
        AtelierTextField(payment, { payment = it.take(500) }, enabled = !saving, minLines = 2, label = { Text("Payment instructions") }, modifier = Modifier.fillMaxWidth())
        AtelierTextField(logo, { logo = it.take(1000) }, enabled = !saving, singleLine = true, label = { Text("Logo link (https)") }, modifier = Modifier.fillMaxWidth())
        AtelierTextField(color, { color = it.take(9) }, enabled = !saving, singleLine = true, label = { Text("Brand colour (#RRGGBB)") }, modifier = Modifier.fillMaxWidth())
        Text("Name, address, currency and timezone are changed from the web app.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        PrimaryAction({ viewModel.saveIdentity(abn, phone, email, payment, logo, color) }, Modifier.fillMaxWidth().testTag("identity-save"), enabled = !saving) { Text(if(saving) "Saving…" else "Save shop details") }
        if(saving) LinearProgressIndicator(Modifier.fillMaxWidth())
    }
}
