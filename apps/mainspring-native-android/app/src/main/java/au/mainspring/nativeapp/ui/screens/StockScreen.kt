package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.StockViewModel
import au.mainspring.nativeapp.ui.formatShopDate

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StockScreen(onBack: () -> Unit, onOpenStocktake: (String) -> Unit, model: StockViewModel = viewModel()) {
    val state by model.state.collectAsStateWithLifecycle()
    var createOpen by remember { mutableStateOf(false) }
    var reviewOpen by remember { mutableStateOf(false) }
    var existingId by remember { mutableStateOf<String?>(null) }
    androidx.activity.compose.BackHandler(state.creating) {}
    Scaffold(topBar = { TopAppBar(title = { Text("Inventory and stocktakes", style = MaterialTheme.typography.headlineSmall) }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onBack, enabled = !state.creating) }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                OutlinedTextField(state.search, model::search, enabled = !state.creating && !state.unknownCreate, label = { Text("Search item code or description") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(state.group, model::group, enabled = !state.creating && !state.unknownCreate, label = { Text("Group code") }, modifier = Modifier.fillMaxWidth())
                FilterChip(state.hideZero, { model.hideZero(!state.hideZero) }, enabled = !state.creating && !state.unknownCreate, label = { Text("Hide zero stock") })
                OutlinedButton(model::refresh, enabled = !state.loading && !state.creating) { Text("Refresh inventory") }
                if(state.createdId != null) {
                    Button({ onOpenStocktake(state.createdId!!) }) { Text("Open created stocktake") }
                    TextButton(model::another) { Text("Start another stocktake") }
                } else {
                    Button({ createOpen = true }, enabled = !state.loading && !state.creating && !state.unknownCreate) { Text(if(state.creating) "Creating stocktake…" else "New stocktake from filters") }
                }
                if(state.unknownCreate) {
                    Text("Creation has no confirmed result. Refresh and review the stocktake directory before creating another.")
                    TextButton({ reviewOpen = true }, enabled = state.directoryReviewed) { Text("Reviewed directory; no stocktake was created") }
                }
            }
            item { Text("Stocktake sessions", style = MaterialTheme.typography.titleLarge) }
            state.sessionsError?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
            items(state.sessions, key = { "session/${it.id}" }) { session ->
                OutlinedCard(onClick = { onOpenStocktake(session.id) }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp)) {
                        Text(session.name, style = MaterialTheme.typography.titleMedium)
                        Text("${session.status} · ${session.progress?.counted ?: 0}/${session.progress?.total ?: 0} counted")
                        Text(formatShopDate(session.createdAt), style = MaterialTheme.typography.bodySmall)
                        if(state.unknownCreate && state.directoryReviewed) TextButton({ existingId = session.id }) { Text("Use this as the created stocktake") }
                    }
                }
            }
            item { Text("Inventory · ${state.items.size} of ${state.total}", style = MaterialTheme.typography.titleLarge) }
            if(state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
            items(state.items, key = { "item/${it.id}" }) { item ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(item.code, style = MaterialTheme.typography.titleMedium)
                        Text(item.fullDescription ?: item.description ?: "Description unavailable")
                        Text("Group ${item.group} ${item.groupName.orEmpty()}")
                        Text("System stock: ${item.quantity} ${item.unit.orEmpty()}")
                        Text("Pack: ${item.packQuantity} ${item.pack.orEmpty()}", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            if(!state.loading && state.items.isEmpty() && state.error == null) item { Text("No inventory matches these filters.") }
            if(state.items.size < state.total) item { Button(model::more, enabled = !state.loading) { Text("Load more inventory") } }
        }
    }
    if(createOpen) AlertDialog(onDismissRequest = { createOpen = false }, title = { Text("Create a stocktake?", style = MaterialTheme.typography.headlineSmall) }, text = {
        Column {
            OutlinedTextField(state.name, model::name, label = { Text("Stocktake name") })
            Text("This snapshots all inventory matching search '${state.search.ifBlank { "All" }}', group '${state.group.ifBlank { "All" }}', hide zero stock: ${state.hideZero}. Matching items beyond the loaded page are included.")
        }
    }, confirmButton = { TextButton({ createOpen = false; model.create() }) { Text("Confirm creation") } }, dismissButton = { TextButton({ createOpen = false }) { Text("Cancel") } })
    if(reviewOpen || existingId != null) AlertDialog(onDismissRequest = { reviewOpen = false; existingId = null }, title = { Text("Confirm directory review", style = MaterialTheme.typography.headlineSmall) },
        text = { Text(if(existingId != null) "Use the selected existing stocktake and clear the interrupted creation checkpoint?" else "I checked the refreshed directory and confirmed the previous creation did not save. A new creation can now be attempted.") },
        confirmButton = { TextButton({ existingId?.let(model::useExisting) ?: model.reviewedNotCreated(); existingId = null; reviewOpen = false }) { Text("Confirm review") } },
        dismissButton = { TextButton({ reviewOpen = false; existingId = null }) { Text("Cancel") } })
}
