package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.QuoteJobPickerViewModel
import au.mainspring.nativeapp.daysInShop
import au.mainspring.nativeapp.quotableJobs
import au.mainspring.nativeapp.ui.ErrorBanner
import au.mainspring.nativeapp.ui.statusLabel

/**
 * "+ New Quote" job picker: search open watch repair jobs by job number, title or customer and pick one.
 * Quotes are written per watch job, so [onPick] hands back the job id for the existing quote composer.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuoteJobPickerSheet(onDismiss: () -> Unit, onPick: (String) -> Unit, viewModel: QuoteJobPickerViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val shown = quotableJobs(state.jobs, state.query)
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxWidth().testTag("quote-job-picker").navigationBarsPadding().padding(horizontal = 20.dp).padding(bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Choose a job to quote", Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge)
            FinSearchField(state.query, viewModel::setQuery, "Search job number, title or customer", Modifier.fillMaxWidth(), fieldTag = "quote-job-search")
            if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { ErrorBanner(it, onRetry = viewModel::refresh) }
            if(!state.loading && state.error == null && shown.isEmpty()) FinEmptyCard(if(state.query.isBlank()) "No open jobs to quote." else "No jobs match your search.")
            LazyColumn(Modifier.heightIn(max = 420.dp).testTag("quote-job-results"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(shown, key = { it.id }) { job ->
                    ServiceJobCard({ onPick(job.id) }, "#${job.jobNumber}", job.title, job.customerName, statusLabel(job.status), job.status,
                        shortDaysInShop(daysInShop(job.createdAt)), null, modifier = Modifier.testTag("quote-job-${job.id}"))
                }
            }
        }
    }
}
