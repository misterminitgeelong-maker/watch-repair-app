package au.mainspring.nativeapp.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.DatabaseExport
import au.mainspring.nativeapp.DatabaseViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.saveReportExport
import au.mainspring.nativeapp.ui.BackLargeHeader
import au.mainspring.nativeapp.ui.EmptyState
import au.mainspring.nativeapp.ui.ErrorBanner
import au.mainspring.nativeapp.ui.FlatPanel
import au.mainspring.nativeapp.ui.MetricStrip
import au.mainspring.nativeapp.ui.SectionLabel
import au.mainspring.nativeapp.ui.TabChip
import au.mainspring.nativeapp.userMessage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.math.BigDecimal

private fun dbAmount(cents: Long) = "$" + BigDecimal.valueOf(cents, 2).toPlainString()
private fun targetLabel(target: String) = when(target) { "shoe" -> "Shoe repairs"; "mobile" -> "Mobile services"; else -> "Watch repairs" }

@Composable
fun DatabaseScreen(onBack: () -> Unit, viewModel: DatabaseViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var pending by remember { mutableStateOf<DatabaseExport?>(null) }
    var generation by remember { mutableStateOf(0L) }
    var confirmImport by rememberSaveable { mutableStateOf(false) }

    fun saveExport(uri: android.net.Uri?) {
        val kind = pending
        if(uri == null || kind == null) { viewModel.setExportBusy(null); return }
        scope.launch {
            viewModel.setExportBusy(kind)
            try {
                check(TokenStore.sessionGeneration() == generation) { "The signed-in shop changed. Choose the export again." }
                val bytes = viewModel.download(kind)
                try { saveReportExport(context, uri, bytes) }
                catch(e: java.io.IOException) { throw IllegalStateException("Could not save the file. Choose another file location.", e) }
                viewModel.setExportBusy(null, "${kind.label} saved.")
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { viewModel.setExportBusy(null, e.userMessage()) }
        }
    }
    val csvSaver = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { saveExport(it) }
    val jsonSaver = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { saveExport(it) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if(uri != null) viewModel.pick(context, uri) }

    Scaffold(topBar = { BackLargeHeader("More", "Data", "Database", onBack) }) { padding ->
        if(!state.allowed) {
            Box(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
                EmptyState("Owner or manager only", "Exports, GST and imports need an owner or manager account.")
            }
            return@Scaffold
        }
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("database-list"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { SectionLabel("GST collected") }
            item {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("day", "week", "month", "quarter").forEach { period ->
                        TabChip(state.period == period, { viewModel.selectPeriod(period) }, label = { Text(period.replaceFirstChar { it.uppercase() }) })
                    }
                }
            }
            if(state.gstLoading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.gstError?.let { item { ErrorBanner(it, onRetry = viewModel::loadGst) } }
            state.gst?.combined?.let { combined ->
                item {
                    MetricStrip(listOf("GST" to dbAmount(combined.gstCents), "Subtotal" to dbAmount(combined.subtotalCents), "Invoices" to combined.invoiceCount.toString()))
                    Text("GST on paid watch and mobile invoices. Shoe repairs have no GST tracking.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                item {
                    FlatPanel {
                        listOf("Watch" to state.gst?.watch, "Mobile services" to state.gst?.mobile).forEach { (label, row) ->
                            if(row != null) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text("$label (${row.invoiceCount} invoices)", style = MaterialTheme.typography.bodySmall)
                                Text(dbAmount(row.gstCents), style = MaterialTheme.typography.labelLarge)
                            }
                        }
                    }
                }
            }

            item { SectionLabel("Export") }
            item {
                FlatPanel {
                    Text("Download your data. Choose where to save the file; Drive or email can be picked there.", style = MaterialTheme.typography.bodySmall)
                    DatabaseExport.entries.forEach { kind ->
                        LinkAction({
                            pending = kind; generation = TokenStore.sessionGeneration()
                            if(kind == DatabaseExport.MyData) jsonSaver.launch(kind.fileName) else csvSaver.launch(kind.fileName)
                        }, enabled = state.exportBusy == null, modifier = Modifier.fillMaxWidth().testTag("export-${kind.name}")) {
                            Text(if(state.exportBusy == kind) "Preparing…" else kind.label)
                        }
                    }
                    state.exportInfo?.let { Text(it, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.testTag("export-info")) }
                }
            }

            item { SectionLabel("Import") }
            item {
                FlatPanel {
                    Text("Bring job history from CSV or Excel into one module. Preview first; nothing is written until you confirm.", style = MaterialTheme.typography.bodySmall)
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("watch", "shoe", "mobile").forEach { t ->
                            TabChip(state.target == t, { viewModel.selectTarget(t) }, label = { Text(targetLabel(t)) })
                        }
                    }
                    LinkAction({ picker.launch(arrayOf("text/csv", "text/comma-separated-values", "application/csv", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/plain")) },
                        enabled = !state.importBusy, modifier = Modifier.fillMaxWidth().testTag("import-pick")) { Text(if(state.picked == null) "Choose a CSV or Excel file" else "Choose a different file") }
                    state.picked?.let { file ->
                        Text(file.name, style = MaterialTheme.typography.titleSmall)
                        Text(if(file.rowCount >= 0) "${file.rowCount} data rows found, ${file.bytes.size / 1024} KB" else "Excel file, ${file.bytes.size / 1024} KB (rows are counted by the server)", style = MaterialTheme.typography.bodySmall, modifier = Modifier.testTag("import-preview"))
                        if(file.isExcel) OutlinedTextField(state.sheetName, viewModel::setSheetName, label = { Text("Excel sheet name (optional)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            LinkAction({ viewModel.runImport(dryRun = true) }, enabled = !state.importBusy, modifier = Modifier.weight(1f).testTag("import-dry-run")) { Text("Dry run") }
                            Button({ confirmImport = true }, enabled = !state.importBusy, modifier = Modifier.weight(1f).testTag("import-run")) { Text("Import…") }
                        }
                    }
                    if(state.importBusy) LinearProgressIndicator(Modifier.fillMaxWidth())
                }
            }
            state.importError?.let { item { ErrorBanner(it) } }
            state.importResult?.let { result ->
                item {
                    FlatPanel {
                        Text(if(result.dryRun) "Dry run complete (nothing written)" else "Import complete", style = MaterialTheme.typography.titleMedium)
                        MetricStrip(listOf("Imported" to result.imported.toString(), "Skipped" to result.skipped.toString(), "Rows" to result.totalRows.toString()))
                        Text("Customers created: ${result.customersCreated}", style = MaterialTheme.typography.bodySmall)
                        result.duplicateCustomerRows?.takeIf { it > 0 }?.let { Text("Duplicate customer rows in file: $it", style = MaterialTheme.typography.bodySmall) }
                        result.sourceSheet?.let { Text("Excel sheet: $it", style = MaterialTheme.typography.bodySmall) }
                        val reasons = result.skippedReasons.orEmpty()
                        if(reasons.isNotEmpty()) {
                            Text("Skipped rows by reason", style = MaterialTheme.typography.labelLarge)
                            reasons.forEach { (reason, count) -> Text("$reason: $count", style = MaterialTheme.typography.bodySmall, modifier = Modifier.testTag("skip-reason")) }
                        }
                    }
                }
            }
        }
    }
    if(confirmImport) {
        val file = state.picked
        AlertDialog(onDismissRequest = { confirmImport = false },
            title = { Text("Import into ${targetLabel(state.target)}?") },
            text = { Text("This adds ${file?.let { if(it.rowCount >= 0) "${it.rowCount} rows from " else "rows from " }.orEmpty()}${file?.name.orEmpty()} to your shop. Existing data is not replaced, but imported records cannot be undone in bulk.") },
            confirmButton = { TextButton({ confirmImport = false; viewModel.runImport(dryRun = false) }) { Text("Import") } },
            dismissButton = { TextButton({ confirmImport = false }) { Text("Cancel") } })
    }
}
