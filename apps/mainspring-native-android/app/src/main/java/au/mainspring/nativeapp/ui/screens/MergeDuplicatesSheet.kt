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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.MergeDuplicatesViewModel
import au.mainspring.nativeapp.api.CustomerRead
import au.mainspring.nativeapp.mergeCandidates
import au.mainspring.nativeapp.ui.ErrorBanner

/**
 * Customers "Merge duplicates": pick the customer to keep, pick the duplicate, confirm, merge. Candidates come from the
 * customers already loaded on the list. [onMerged] refreshes that list.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MergeDuplicatesSheet(customers: List<CustomerRead>, onDismiss: () -> Unit, onMerged: () -> Unit, viewModel: MergeDuplicatesViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var keepId by rememberSaveable { mutableStateOf<String?>(null) }
    var duplicateId by rememberSaveable { mutableStateOf<String?>(null) }
    var query by rememberSaveable { mutableStateOf("") }
    val keep = customers.firstOrNull { it.id == keepId }
    val duplicate = customers.firstOrNull { it.id == duplicateId }
    val done = state.mergedKeepName
    ModalBottomSheet(onDismissRequest = { if(!state.merging) { viewModel.noticeShown(); onDismiss() } }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxWidth().testTag("merge-sheet").navigationBarsPadding().padding(horizontal = 20.dp).padding(bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Merge duplicates", Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge)
            when {
                done != null -> {
                    FinCard(Modifier.testTag("merge-success")) { Text("Merged. The duplicate was removed and its watches and jobs now belong to $done.", style = MaterialTheme.typography.bodyLarge) }
                    FinPrimaryButton("Done", { viewModel.noticeShown(); onDismiss() }, Modifier.testTag("merge-done"))
                }
                keep != null && duplicate != null -> {
                    Text("Check before merging", style = MaterialTheme.typography.titleMedium)
                    MergeCustomerCard("Keep", keep, "merge-keep-card")
                    MergeCustomerCard("Remove (duplicate)", duplicate, "merge-duplicate-card")
                    Text("${duplicate.fullName}'s watches, shoe jobs and mobile jobs move to ${keep.fullName}, and ${duplicate.fullName} is permanently removed. This cannot be undone.", style = MaterialTheme.typography.bodyMedium)
                    state.error?.let { ErrorBanner(it) }
                    if(state.merging) LinearProgressIndicator(Modifier.fillMaxWidth())
                    FinPrimaryButton(if(state.error != null) "Try again" else "Merge and delete duplicate", { viewModel.merge(keep, duplicate, onMerged) }, Modifier.testTag("merge-confirm"), enabled = !state.merging)
                    FinOutlinedLabel("Back", { viewModel.clearError(); duplicateId = null; query = "" }, Modifier.fillMaxWidth().testTag("merge-back"), enabled = !state.merging)
                }
                else -> {
                    val choosingKeep = keep == null
                    Text(if(choosingKeep) "Step 1 of 2: pick the customer to keep" else "Step 2 of 2: pick the duplicate to merge into ${keep?.fullName}", style = MaterialTheme.typography.titleMedium)
                    FinSearchField(query, { query = it }, "Search name, phone or email", Modifier.fillMaxWidth(), fieldTag = "merge-search")
                    val rows = mergeCandidates(customers, query, excludeId = keepId)
                    if(rows.isEmpty()) FinEmptyCard(if(customers.isEmpty()) "No customers loaded yet." else "No customers match your search.")
                    LazyColumn(Modifier.heightIn(max = 380.dp).testTag("merge-results"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(rows, key = { it.id }) { c ->
                            FinCard(Modifier.testTag("merge-pick-${c.id}"), onClick = { query = ""; if(choosingKeep) keepId = c.id else duplicateId = c.id }) { MergeCustomerLines(c) }
                        }
                    }
                    if(!choosingKeep) FinOutlinedLabel("Back", { keepId = null; query = "" }, Modifier.fillMaxWidth().testTag("merge-back"))
                }
            }
        }
    }
}

@Composable private fun MergeCustomerCard(role: String, c: CustomerRead, tag: String) {
    FinCard(Modifier.testTag(tag)) {
        Text(role, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        MergeCustomerLines(c)
    }
}

@Composable private fun MergeCustomerLines(c: CustomerRead) {
    Text(c.fullName, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
    Text(c.phone?.takeIf { it.isNotBlank() } ?: "No phone", style = MaterialTheme.typography.bodyMedium)
    Text(c.email?.takeIf { it.isNotBlank() } ?: "No email", style = MaterialTheme.typography.bodyMedium)
}
