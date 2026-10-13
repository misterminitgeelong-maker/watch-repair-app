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
    Scaffold(topBar = { TopAppBar(title = { Text("Job quotes", style = MaterialTheme.typography.headlineSmall) }, navigationIcon = { TextButton(onClick = onBack) { Text("Back") } }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            state.job?.let { Text("${it.jobNumber} · ${it.title}", style = MaterialTheme.typography.titleMedium) }
            if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            OutlinedButton(onClick = vm::load, enabled = !state.loading && !state.busy) { Text("Refresh quotes") }
            if(state.unknownSave) OutlinedButton(onClick = vm::acknowledgeHistory, enabled = !state.loading && state.historyChecked) { Text("I checked for the saved quote") }
            state.quotes.forEach { q ->
                OutlinedButton(onClick = { onOpenQuote(q.id) }, modifier = Modifier.fillMaxWidth()) { Text("${q.status.replace('_',' ')} · ${formatCents(q.totalCents, q.currency)}") }
            }
            if (state.created != null) { Text("Quote saved as a draft. Open it to review totals and send it to the customer."); OutlinedButton(onClick = vm::startAnotherQuote) { Text("Create another quote") } }
            else if (!state.unknownSave && state.job != null) {
                HorizontalDivider(); Text("Create quote", style = MaterialTheme.typography.titleLarge)
                QuoteComposer("quote-composer/watch/$jobId", state.job?.customerAccountId != null, !state.busy && !state.loading, catalogue = false, onSave = vm::createLines)
            }
        }
    }
}

