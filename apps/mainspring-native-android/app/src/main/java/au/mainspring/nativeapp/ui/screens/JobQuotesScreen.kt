package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.JobQuotesViewModel
import au.mainspring.nativeapp.ui.formatCents

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobQuotesScreen(jobId: String, onBack: () -> Unit, onOpenQuote: (String) -> Unit) {
    val vm: JobQuotesViewModel = viewModel(key = jobId, factory = JobQuotesViewModel.factory(jobId))
    val state by vm.state.collectAsStateWithLifecycle()
    val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
    var copiedQuote by remember { mutableStateOf<String?>(null) }
    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Job quotes") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            state.job?.let { if(au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.MonoLabel("Quotes / ${state.quotes.size}"); Text("${it.jobNumber} · ${it.title}", style = MaterialTheme.typography.titleMedium) }
            if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            androidx.compose.material3.TextButton(onClick = vm::load, enabled = !state.loading && !state.busy) { Text("Refresh") }
            if(state.unknownSave) OutlinedButton(onClick = vm::acknowledgeHistory, enabled = !state.loading && state.historyChecked) { Text("I checked for the saved quote") }
            state.quotes.forEach { q ->
                au.mainspring.nativeapp.ui.ListCard({ onOpenQuote(q.id) }) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        au.mainspring.nativeapp.ui.StatusPill(q.status)
                        Text(formatCents(q.totalCents, q.currency), style = MaterialTheme.typography.titleMedium)
                    }
                    Text(au.mainspring.nativeapp.ui.formatShopDate(q.createdAt).substringBefore(' '), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    val token = q.approvalToken?.takeIf { it.isNotBlank() }
                    if (token != null && (q.status == "sent" || q.status == "expired")) androidx.compose.material3.TextButton(onClick = {
                        clipboard.setText(androidx.compose.ui.text.AnnotatedString(au.mainspring.nativeapp.api.quoteApprovalLink(au.mainspring.nativeapp.api.ApiClient.getEffectiveBaseUrl(), token)))
                        copiedQuote = q.id
                    }, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (copiedQuote == q.id) "Approval link copied" else "Copy approval link") }
                }
            }
            if (state.created != null) { if(au.mainspring.nativeapp.ui.LocalCalibre.current) CalibreNotice("Quote saved as a draft. Open it to review totals and send it to the customer.") else Text("Quote saved as a draft. Open it to review totals and send it to the customer."); OutlinedButton(onClick = vm::startAnotherQuote) { Text("Create another quote") } }
            else if (!state.unknownSave && state.job != null) {
                au.mainspring.nativeapp.ui.SectionLabel("Create a new quote")
                QuoteComposer("quote-composer/watch/$jobId", state.job?.customerAccountId != null, !state.busy && !state.loading, catalogue = false, onSave = vm::createLines)
            }
        }
    }
}

