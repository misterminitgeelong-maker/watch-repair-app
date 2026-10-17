package au.mainspring.nativeapp.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.OrderImportViewModel
import au.mainspring.nativeapp.ui.*

/** Customer Orders import: choose a CSV/Excel file, preview with a dry run, then import. */
@Composable fun OrderImportDialog(onDismiss: () -> Unit, onImported: () -> Unit, viewModel: OrderImportViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var confirm by remember { mutableStateOf(false) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if(uri != null) viewModel.pick(context, uri) }
    AlertDialog(onDismissRequest = { if(!state.busy) onDismiss() }, title = { Text("Import customer orders") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()).testTag("order-import"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Bring orders in from a CSV or Excel file. Run a dry run first; nothing is written until you import.", style = MaterialTheme.typography.bodySmall)
                SecondaryAction({ picker.launch(arrayOf("text/csv", "text/comma-separated-values", "application/csv", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/plain")) },
                    Modifier.fillMaxWidth().testTag("order-import-pick"), enabled = !state.busy) { Text(if(state.picked == null) "Choose a file" else "Choose a different file") }
                state.picked?.let { file ->
                    Text(file.name, style = MaterialTheme.typography.titleSmall)
                    Text(if(file.rowCount >= 0) "${file.rowCount} data rows found" else "Excel file, ${file.bytes.size / 1024} KB", style = MaterialTheme.typography.bodySmall, modifier = Modifier.testTag("order-import-preview"))
                    if(state.sheets.size > 1) {
                        MonoLabel("Sheet")
                        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            state.sheets.forEach { s -> TabChip(state.sheet == s, { viewModel.selectSheet(s) }, { Text(s) }) }
                        }
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        SecondaryAction({ viewModel.run(true) }, Modifier.weight(1f).testTag("order-import-dry"), enabled = !state.busy) { Text("Dry run") }
                        PrimaryAction({ confirm = true }, Modifier.weight(1f).testTag("order-import-run"), enabled = !state.busy) { Text("Import") }
                    }
                }
                if(state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { ErrorBanner(it) }
                state.result?.let { r ->
                    FlatPanel {
                        Text(if(r.dryRun) "Dry run complete (nothing written)" else "Import complete", style = MaterialTheme.typography.titleSmall, modifier = Modifier.testTag("order-import-result"))
                        MetricStrip(listOf("Imported" to r.imported.toString(), "Skipped" to r.skipped.toString(), "Rows" to r.totalRows.toString()))
                        r.skippedReasons.orEmpty().forEach { (reason, n) -> Text("$reason: $n", style = MaterialTheme.typography.bodySmall) }
                    }
                }
            }
        },
        confirmButton = { TextButton({ viewModel.reset(); onDismiss() }, enabled = !state.busy) { Text("Close") } })
    if(confirm) AlertDialog(onDismissRequest = { confirm = false }, title = { Text("Import these orders?") },
        text = { Text("This adds orders from ${state.picked?.name.orEmpty()} to your shop. Imported orders can only be removed one at a time.") },
        confirmButton = { TextButton({ confirm = false; viewModel.run(false, onImported) }, modifier = Modifier.testTag("order-import-confirm")) { Text("Import") } },
        dismissButton = { TextButton({ confirm = false }) { Text("Cancel") } })
}
