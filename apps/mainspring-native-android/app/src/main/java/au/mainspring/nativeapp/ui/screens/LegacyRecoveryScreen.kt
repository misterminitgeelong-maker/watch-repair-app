package au.mainspring.nativeapp.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.ui.*
import com.google.gson.JsonElement
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private fun legacyLabel(key: String): String = key.replace(Regex("([a-z])([A-Z])"), "$1 $2").replace('_', ' ').replaceFirstChar { it.uppercase() }
private fun readableLegacyFields(value: JsonElement, prefix: String = ""): List<Pair<String, String>> = when {
    value.isJsonObject -> value.asJsonObject.entrySet().flatMap { (key, child) -> readableLegacyFields(child, listOf(prefix.takeIf(String::isNotBlank), legacyLabel(key)).filterNotNull().joinToString(" · ")) }
    value.isJsonArray -> value.asJsonArray.flatMapIndexed { index, child -> readableLegacyFields(child, "$prefix ${index + 1}") }
    value.isJsonNull -> emptyList()
    else -> value.asString.takeIf(String::isNotBlank)?.let { listOf(prefix to it) }.orEmpty()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun LegacyRecoveryScreen(onBack: () -> Unit, onOpenJob: (String) -> Unit = {}, vm: LegacyRecoveryViewModel = viewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var details by remember { mutableStateOf<Pair<String, JsonElement>?>(null) }
    var exportText by remember { mutableStateOf<String?>(null) }
    val saver = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        val text = exportText; exportText = null
        if(uri != null && text != null) scope.launch { try { check(vm.canExport()) { "Your sign-in changed. Reopen recovery in the current shop before saving a copy." }; withContext(Dispatchers.IO) { check(vm.canExport()) { "Your sign-in changed. Reopen recovery before exporting." }; context.contentResolver.openOutputStream(uri)?.use { output -> check(vm.canExport()) { "Your sign-in changed. Nothing was exported." }; output.write(text.toByteArray(Charsets.UTF_8)) } ?: error("Could not save the recovery file.") } } catch(e: Exception) { vm.error(e) } }
    }
    Scaffold(topBar = { AtelierTopAppBar(title = { Text("Previous app work") }, navigationIcon = { BackButton(onClick = onBack) }, actions = { TextButton(vm::refresh, enabled = !s.loading && !s.busy) { Text("Refresh") } }) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("legacy-recovery"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text("Work saved on this phone before the native app update is preserved here. Only records matched to your current shop and account are shown.", style = MaterialTheme.typography.bodyMedium)
                Text("Review saved details before continuing in the new app. Photos in old intake drafts were stored as names only and need to be selected again.", style = MaterialTheme.typography.bodySmall)
                if(s.loading || s.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                s.error?.let { ErrorBanner(it) }
                s.info?.let { Text(it, color = MaterialTheme.colorScheme.primary) }
                if(!s.scanned && !s.loading) TextButton(vm::scan) { Text("Check previous app storage") }
            }
            if(s.scanned && !s.loading && s.drafts.isEmpty() && s.writes.isEmpty() && s.unmatched == 0) item { EmptyState("No previous work for this account", "There are no matched saved drafts or offline changes in the current shop.") }
            if(s.drafts.isNotEmpty()) item { SectionLabel("SAVED INTAKE DRAFTS") }
            items(s.drafts, key = { it.key + ":" + it.envelope.hashCode() }) { draft ->
                val title = when(draft.kind) { "watch-intake" -> "Watch intake"; "shoe-intake" -> "Shoe intake"; "mobile-services-intake" -> "Mobile services intake"; else -> "Saved intake" }
                FlatPanel {
                    Text(title, style = MaterialTheme.typography.titleMedium)
                    draft.envelope.get("savedAt")?.runCatching { java.time.Instant.ofEpochMilli(asLong).toString() }?.getOrNull()?.let { Text("Saved ${formatShopDate(it)}", style = MaterialTheme.typography.bodySmall) }
                    Text("The original draft remains preserved while you finish the record in the new intake screen.")
                    Row {
                        TextButton({ details = title to (draft.data ?: draft.envelope) }, modifier = Modifier.testTag("legacy-view-draft")) { Text("View saved details") }
                        TextButton({ try { exportText = vm.exportDraft(draft); saver.launch("mainspring-previous-${draft.kind}.json") } catch(e: Exception) { vm.error(e) } }) { Text("Save a copy") }
                    }
                }
            }
            if(s.writes.isNotEmpty()) item { SectionLabel("SAVED OFFLINE CHANGES") }
            items(s.writes, key = { it.id }) { write ->
                FlatPanel {
                    Text(write.title.ifBlank { "Saved job change" }, style = MaterialTheme.typography.titleMedium)
                    Text(if(write.dead) "Needs manual review" else "Saved offline change", color = MaterialTheme.colorScheme.primary)
                    write.liveStatus?.let { Text("Current job status: ${watchStatusLabel(it)}", style = MaterialTheme.typography.bodySmall) }
                    SelectionContainer { Column { readableLegacyFields(write.target.body).forEach { (label, value) -> DetailRow(label, value) } } }
                    Row {
                        TextButton({ onOpenJob(when { write.target.readPath.contains("/repair-jobs/") -> "watchJob/"; write.target.readPath.contains("/shoe-repair-jobs/") -> "shoeJob/"; else -> "autoKeyJob/" } + write.target.jobId) }) { Text("Open job") }
                        TextButton({ try { exportText = vm.exportWrite(write); saver.launch("mainspring-previous-change.json") } catch(e: Exception) { vm.error(e) } }) { Text("Save a copy") }
                    }
                    Text("Open the current job to finish this change manually, after checking whether it was already saved. The previous request is kept for reference and is never resubmitted here.", style = MaterialTheme.typography.bodySmall)
                }
            }
            if(s.unmatched > 0) item { FlatPanel {
                Text("${s.unmatched} earlier changes could not be matched to this shop.", style = MaterialTheme.typography.titleMedium)
                Text("They remain preserved on this phone. Switch to the shop where you made them, then reopen recovery. Changes that created new records or moved money need manual support review and are never replayed here.")
            } }
        }
    }
    details?.let { (title, value) -> AlertDialog(onDismissRequest = { details = null }, title = { Text(title) }, text = {
        SelectionContainer { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) { readableLegacyFields(value).forEach { (label, text) -> Text(label, style = MaterialTheme.typography.labelLarge); Text(text, style = MaterialTheme.typography.bodyMedium) } } }
    }, confirmButton = { TextButton({ details = null }) { Text("Close") } }) }
}
