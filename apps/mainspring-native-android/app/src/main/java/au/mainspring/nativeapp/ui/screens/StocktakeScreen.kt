package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.StocktakeViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StocktakeScreen(id: String, onBack: () -> Unit, model: StocktakeViewModel = viewModel(factory = object: androidx.lifecycle.ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST") override fun <T: androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T = StocktakeViewModel(id) as T
})) {
    val state by model.state.collectAsStateWithLifecycle()
    var confirm by remember { mutableStateOf(false) }
    var completeOpen by remember { mutableStateOf(false) }
    var completionReview by remember { mutableStateOf(false) }
    val allLines = state.session?.lines.orEmpty()
    val matched = allLines.count {it.counted != null && it.counted == it.expected}
    val shortage = allLines.count {it.counted != null && it.counted < it.expected}
    val over = allLines.count {it.counted != null && it.counted > it.expected}
    val scroll = androidx.compose.foundation.lazy.rememberLazyListState()
    LaunchedEffect(state.lineId) { if(state.lineId.isNotBlank()) scroll.animateScrollToItem(0) }
    BackHandler(state.busy) {}
    Scaffold(topBar = { TopAppBar(title = { Text("Stocktake counts", style = MaterialTheme.typography.headlineSmall) }, navigationIcon = { TextButton(onBack, enabled = !state.busy) { Text("Back") } }) }) { padding ->
        val lines = state.session?.lines.orEmpty().filter { line ->
            (!state.hideCounted || line.counted == null) && (state.search.isBlank() || listOf(line.code, line.group, line.description.orEmpty(), line.shortDescription.orEmpty()).any { it.contains(state.search, true) })
        }
        LazyColumn(Modifier.fillMaxSize().padding(padding), state = scroll, contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                state.session?.let { Text("${it.name} · ${it.status}", style = MaterialTheme.typography.titleLarge) }
                Text("Progress ${allLines.count {it.counted != null}} / ${allLines.size}",style=MaterialTheme.typography.labelLarge)
                LinearProgressIndicator(progress={if(allLines.isEmpty()) 0f else allLines.count {it.counted != null}.toFloat()/allLines.size},modifier=Modifier.fillMaxWidth())
                au.mainspring.nativeapp.ui.MetricStrip(listOf("Matched" to matched.toString(),"Shortage" to shortage.toString(),"Over" to over.toString()))
                OutlinedButton(model::refresh, enabled = !state.loading && !state.busy) { Text("Refresh counts") }
                if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                state.info?.let { Text(it) }
                if(state.uncertain) {
                    Text("The last save has no confirmed result. Refresh and compare the stored count before retrying.")
                    TextButton(model::reviewNotSaved, enabled = state.reviewed && !state.loading) { Text("Reviewed latest count; allow a new save") }
                }
                if(state.completionUnknown) {
                    Text("Completion has no confirmed result. Refresh the stocktake before making further changes.")
                    TextButton({ completionReview = true }, enabled = state.reviewed && !state.loading && state.editable) { Text("Reviewed; stocktake is still in progress") }
                }
                if(state.editable && au.mainspring.nativeapp.TokenStore.canManageInvoices()) Button({ completeOpen = true },
                    enabled = !state.loading && !state.busy && !state.uncertain && !state.completionUnknown && state.lineId.isBlank()) { Text("Complete stocktake") }
                state.report?.let { report ->
                    Text("Summary: ${report.matched} matched · ${report.missing} short · ${report.over} over")
                    Text("Quantity variance: ${report.varianceQuantity}")
                    Text("Variance value: ${java.math.BigDecimal.valueOf(report.varianceValue, 2).toPlainString()} (currency not supplied by API)")
                }
            }
            if(state.lineId.isNotBlank()) item {
                val selected = state.session?.lines.orEmpty().find { it.id == state.lineId }
                Card {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Count ${selected?.code ?: state.lineId}", style = MaterialTheme.typography.titleMedium)
                        Text("Latest stored count: ${selected?.counted ?: "Not counted"}")
                        OutlinedTextField(state.count, model::count, label = { Text("Counted quantity") }, enabled = !state.busy && !state.uncertain, modifier = Modifier.fillMaxWidth())
                        OutlinedTextField(state.notes, model::notes, label = { Text("Count notes") }, enabled = !state.busy && !state.uncertain, modifier = Modifier.fillMaxWidth())
                        FilterChip(state.allowNegative, { model.negative(!state.allowNegative) }, enabled = !state.busy && !state.uncertain, label = { Text("Allow negative count") })
                        Button({ confirm = true }, enabled = state.editable && !state.loading && !state.busy && !state.uncertain && !state.completionUnknown && !state.conflict) { Text("Save count") }
                        TextButton(model::discard, enabled = !state.busy && !state.uncertain) { Text("Discard count draft") }
                    }
                }
            }
            item {
                OutlinedTextField(state.search, model::search, label = { Text("Find item in this stocktake") }, modifier = Modifier.fillMaxWidth())
                FilterChip(state.hideCounted, { model.hideCounted(!state.hideCounted) }, label = { Text("Only uncounted items") })
                Text("${lines.size} items shown. Counts are saved to this session; inventory updates when the stocktake is completed.", style = MaterialTheme.typography.bodySmall)
            }
            items(lines, key = { it.id }) { line ->
                Card(Modifier.fillMaxWidth(),colors=CardDefaults.cardColors(containerColor=MaterialTheme.colorScheme.surface)) {
                    Column(Modifier.padding(16.dp)) {
                        Text(line.code, style = MaterialTheme.typography.titleMedium)
                        Text(line.description ?: line.shortDescription ?: "Description unavailable")
                        Text("System ${line.expected} · Counted ${line.counted ?: "Pending"}",style=MaterialTheme.typography.bodySmall)
                        line.systemQuantity?.takeIf { it != line.expected }?.let { Text("Current system stock: $it") }
                        line.variance?.let { Text("Variance: $it") }
                        line.notes?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                        if(state.editable) TextButton({ model.select(line) }, enabled = state.lineId.isBlank() && !state.loading && !state.busy && !state.uncertain && !state.completionUnknown) { Text("Count ${line.code}") }
                    }
                }
            }
        }
    }
    if(confirm) AlertDialog(onDismissRequest = { confirm = false }, title = { Text("Save this stocktake count?", style = MaterialTheme.typography.headlineSmall) }, text = { Text("Quantity ${state.count}. The existing count and notes for this item will be replaced after checking for changes.") },
        confirmButton = { TextButton({ confirm = false; model.save() }) { Text("Confirm save") } }, dismissButton = { TextButton({ confirm = false }) { Text("Cancel") } })
    if(completeOpen) AlertDialog(onDismissRequest = { completeOpen = false }, title = { Text("Complete and update inventory?", style = MaterialTheme.typography.headlineSmall) },
        text = { Text("All ${state.session?.lines?.size ?: 0} items must be counted. Completing replaces their system stock quantities with the saved counts and locks this stocktake. Review counts before confirming.") },
        confirmButton = { TextButton({ completeOpen = false; model.complete() }) { Text("Confirm completion") } }, dismissButton = { TextButton({ completeOpen = false }) { Text("Cancel") } })
    if(completionReview) AlertDialog(onDismissRequest = { completionReview = false }, title = { Text("Confirm completion review", style = MaterialTheme.typography.headlineSmall) },
        text = { Text("The refreshed stocktake is still in progress. Clear the interrupted completion checkpoint so it can be reviewed and submitted again?") },
        confirmButton = { TextButton({ completionReview = false; model.reviewedNotCompleted() }) { Text("Confirm review") } }, dismissButton = { TextButton({ completionReview = false }) { Text("Cancel") } })
}
