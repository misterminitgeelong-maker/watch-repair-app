package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.material3.ScaffoldDefaults
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.size
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.material3.Surface
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.FilterChip
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.AutoKeyJobsViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AutoKeyJobsScreen(
    onBack: () -> Unit,
    onOpenJob: (String) -> Unit,
    onNewJob: () -> Unit,
    viewModel: AutoKeyJobsViewModel = viewModel(factory = AutoKeyJobsViewModel.listFactory()),
    embedded: Boolean = false,
    onOpenBookingRequests: (() -> Unit)? = null,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var dateOpen by remember { mutableStateOf(false) }
    var filtersOpen by remember { mutableStateOf(false) }
    var bulkStatus by rememberSaveable { mutableStateOf("booking_confirmed") }
    var bulkMenu by remember { mutableStateOf(false) }
    var confirmBulk by remember { mutableStateOf(false) }
    au.mainspring.nativeapp.ui.RefreshOnResume(viewModel::refresh)
    Scaffold(contentWindowInsets = WindowInsets(0, 0, 0, 0), containerColor = androidx.compose.ui.graphics.Color.Transparent) { padding ->
        au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) { LazyColumn(
            Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if(onOpenBookingRequests != null) item { au.mainspring.nativeapp.ui.PendingBookingsBanner(onOpenBookingRequests, Modifier.padding(horizontal = 16.dp)) }
            item {
                Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    SandSegmented(listOf(ToggleOption("active", "Active", "segment-active"), ToggleOption("completed", "Completed", "segment-completed")),
                        if(state.focus == null) state.directory else "", { viewModel.directory(it) })
                    SearchFiltersRow(state.query, viewModel::query, "Search jobs…", { filtersOpen = true }, (if(state.focus != null) 1 else 0) + (if(state.focus == null && state.directory == "all") 1 else 0))
                    au.mainspring.nativeapp.ui.SavedViewsRow(state.savedViews, viewModel::currentView, viewModel::applyView, viewModel::saveView, viewModel::deleteView,
                        Modifier.testTag("mobile-saved-views"), horizontalPadding = 0.dp)
                    state.bulkMessage?.let { Text(it, Modifier.testTag("bulk-message"), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary) }
                    state.bulkError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
                    if(au.mainspring.nativeapp.TokenStore.canWorkJobs()) {
                        if(!state.selecting) TextButton(onClick = viewModel::startSelecting, modifier = Modifier.heightIn(min = 48.dp).testTag("bulk-select")) { Text("Select jobs") }
                        else Column(Modifier.fillMaxWidth().testTag("bulk-bar"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text("${state.selected.size} selected", Modifier.weight(1f), style = MaterialTheme.typography.labelLarge)
                                TextButton(onClick = viewModel::toggleSelectAll, modifier = Modifier.heightIn(min = 48.dp).testTag("bulk-select-all")) { Text("Select all shown") }
                                TextButton(onClick = viewModel::stopSelecting, enabled = !state.bulkBusy, modifier = Modifier.heightIn(min = 48.dp).testTag("bulk-done")) { Text("Done") }
                            }
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                androidx.compose.foundation.layout.Box(Modifier.weight(1f)) {
                                    OutlinedButton(onClick = { bulkMenu = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("bulk-status-picker")) { Text(au.mainspring.nativeapp.ui.statusLabel(bulkStatus), maxLines = 1) }
                                    androidx.compose.material3.DropdownMenu(bulkMenu, { bulkMenu = false }) {
                                        au.mainspring.nativeapp.api.MOBILE_STATUS_PICKER.forEach { (key, label) ->
                                            androidx.compose.material3.DropdownMenuItem(text = { Text(label) }, onClick = { bulkStatus = key; bulkMenu = false }, modifier = Modifier.heightIn(min = 48.dp))
                                        }
                                    }
                                }
                                Button(onClick = { confirmBulk = true }, enabled = state.selected.isNotEmpty() && !state.bulkBusy, modifier = Modifier.heightIn(min = 48.dp).testTag("bulk-apply")) { Text(if(state.bulkBusy) "Updating\u2026" else "Set status") }
                            }
                        }
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text("${state.jobs.size} of ${state.total} " + (if(state.day != null) "appointments" else "jobs") + (if(state.day != null) " · ${au.mainspring.nativeapp.TokenStore.calendarTimezone()}" else ""),
                            Modifier.weight(1f), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        TextButton(onClick = { dateOpen = true }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Schedule by day") }
                    }
                    state.day?.let {
                        Text(au.mainspring.nativeapp.ui.formatShopDate(it), style = MaterialTheme.typography.titleMedium)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            TextButton(onClick = { viewModel.shiftDay(-1) }) { Text("Previous day") }
                            TextButton(onClick = { viewModel.shiftDay(1) }) { Text("Next day") }
                            TextButton(onClick = { viewModel.day(null) }) { Text("Clear date") }
                        }
                    }
                    if(state.loading) androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
                    state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = { viewModel.refresh() }) }
                }
            }
            items(state.jobs, key = { it.id }) { j ->
                val vehicle = listOfNotNull(j.vehicleMake, j.vehicleModel, j.vehicleYear?.toString()).filter { it.isNotBlank() }.joinToString(" ")
                val detail = listOf(vehicle, j.customerName.orEmpty()).filter { it.isNotBlank() }.joinToString(" · ")
                val when_ = if(j.scheduledAt != null) (if(state.day == null) au.mainspring.nativeapp.ui.formatShopDate(j.scheduledAt, au.mainspring.nativeapp.TokenStore.calendarTimezone()) + " " else "") + bookingTime(j.scheduledAt) else null
                val picked = j.id in state.selected
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                if(state.selecting) androidx.compose.material3.Checkbox(picked, { viewModel.toggleSelected(j.id) },
                    Modifier.size(48.dp).testTag("bulk-check-${j.id}").semantics { contentDescription = (if(picked) "Deselect job " else "Select job ") + j.jobNumber })
                ServiceJobCard({ if(state.selecting) viewModel.toggleSelected(j.id) else onOpenJob(j.id) }, j.jobNumber, j.title, detail.ifBlank { null }, au.mainspring.nativeapp.ui.statusLabel(j.status), j.status, when_,
                    j.jobAddress?.takeIf { it.isNotBlank() }, thumb = { au.mainspring.nativeapp.ui.JobThumb("auto_key", j.id, size = 56.dp) },
                    modifier = Modifier.weight(1f),
                    badges = {
                        au.mainspring.nativeapp.slaChip(j)?.let { au.mainspring.nativeapp.ui.SlaChip(it) }
                        if(j.priority == "high" || j.priority == "urgent") au.mainspring.nativeapp.ui.StatusPill("urgent")
                    })
                }
            }
            if(!state.loading && state.jobs.isEmpty() && state.error == null) item { au.mainspring.nativeapp.ui.EmptyState("No jobs match this view", "Try another filter or search.") }
            if(state.jobs.size < state.total) item { OutlinedButton(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) { Text("Load more jobs") } }
        } }
    }
    if(confirmBulk) androidx.compose.material3.AlertDialog(onDismissRequest = { confirmBulk = false },
        title = { Text("Set status for ${state.selected.size} job${if(state.selected.size == 1) "" else "s"}?") },
        text = { Text("Every selected job will be set to ${au.mainspring.nativeapp.ui.statusLabel(bulkStatus)}. This does not send customer messages or create invoices; open a job to complete it properly.") },
        confirmButton = { Button(onClick = { confirmBulk = false; viewModel.bulkSetStatus(bulkStatus) }, modifier = Modifier.heightIn(min = 48.dp).testTag("bulk-confirm")) { Text("Set status") } },
        dismissButton = { TextButton(onClick = { confirmBulk = false }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Cancel") } })
    if(filtersOpen) {
        FiltersSheet(onDismiss = { filtersOpen = false }, onReset = { viewModel.focus(null); viewModel.directory("active") }) {
            FilterSection("Directory") {
                listOf("active" to "Active", "completed" to "Completed", "all" to "All").forEach { (k, v) -> SheetChip(v, state.focus == null && state.directory == k, { viewModel.directory(k) }) }
            }
            FilterSection("Focus") {
                listOf("today" to "Today", "unscheduled" to "Unscheduled", "unassigned" to "Unassigned", "needs_quote" to "Needs quote", "completed_unpaid" to "Completed, unpaid")
                    .forEach { (k, v) -> SheetChip(v, state.focus == k, { viewModel.focus(if(state.focus == k) null else k) }) }
            }
        }
    }
    if(dateOpen) {
        val initial = state.day?.let(java.time.LocalDate::parse) ?: java.time.LocalDate.now(java.time.ZoneId.of(au.mainspring.nativeapp.TokenStore.calendarTimezone()))
        val picker = androidx.compose.material3.rememberDatePickerState(initialSelectedDateMillis = initial.atStartOfDay(java.time.ZoneOffset.UTC).toInstant().toEpochMilli())
        androidx.compose.material3.DatePickerDialog(onDismissRequest = { dateOpen = false },
            confirmButton = { TextButton(onClick = {
                picker.selectedDateMillis?.let { viewModel.day(java.time.Instant.ofEpochMilli(it).atZone(java.time.ZoneOffset.UTC).toLocalDate().toString()) }
                dateOpen = false
            }, enabled = picker.selectedDateMillis != null) { Text("Show appointments") } },
            dismissButton = { TextButton(onClick = { dateOpen = false }) { Text("Cancel") } }) {
            androidx.compose.material3.DatePicker(picker)
        }
    }
}

private fun bookingTime(value: String?): String {
    if(value == null) return "—"
    val zone = java.time.ZoneId.of(au.mainspring.nativeapp.TokenStore.calendarTimezone())
    val local = au.mainspring.nativeapp.bookingInstant(value)?.atZone(zone)?.toLocalTime() ?: return "\u2014"
    return local.format(java.time.format.DateTimeFormatter.ofPattern("HH:mm"))
}
