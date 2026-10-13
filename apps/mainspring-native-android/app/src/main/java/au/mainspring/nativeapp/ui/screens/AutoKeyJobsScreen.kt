package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.material3.ScaffoldDefaults
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.foundation.layout.width
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
    viewModel: AutoKeyJobsViewModel = viewModel(),
    embedded: Boolean = false,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var dateOpen by remember { mutableStateOf(false) }
    au.mainspring.nativeapp.ui.RefreshOnResume(viewModel::refresh)
    Scaffold(contentWindowInsets = WindowInsets(0, 0, 0, 0), containerColor = androidx.compose.ui.graphics.Color.Transparent) { padding ->
        LazyColumn(
            Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            item {
                au.mainspring.nativeapp.ui.AtelierTextField(state.query, viewModel::query, label = { Text("Search jobs, customers or registration") }, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp), singleLine = true)
                au.mainspring.nativeapp.ui.FilterRow(listOf("active" to "Active", "completed" to "Completed", "all" to "All").map { (k, v) -> k as String? to v }, if(state.focus == null) state.directory else null, { viewModel.directory(it ?: "active") })
                au.mainspring.nativeapp.ui.FilterRow(listOf("today" to "Today", "unscheduled" to "Unscheduled", "unassigned" to "Unassigned", "needs_quote" to "Needs quote", "completed_unpaid" to "Completed, unpaid").map { (k, v) -> k as String? to v },
                    state.focus, { viewModel.focus(if(state.focus == it) null else it) })
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { dateOpen = true }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Schedule by day") }
                    state.day?.let { Text(au.mainspring.nativeapp.ui.formatShopDate(it), style = MaterialTheme.typography.titleMedium) }
                    TextButton(onClick = { viewModel.refresh() }, enabled = !state.loading, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") }
                }
                state.day?.let {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(onClick = { viewModel.shiftDay(-1) }) { Text("Previous day") }
                        TextButton(onClick = { viewModel.shiftDay(1) }) { Text("Next day") }
                        TextButton(onClick = { viewModel.day(null) }) { Text("Clear date") }
                    }
                }
                if(state.loading) androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp, vertical = 8.dp), onRetry = { viewModel.refresh() }) }
                Text("${state.jobs.size} of ${state.total} " + (if(state.day != null) "appointments" else "jobs") + (if(state.day != null) " \u00b7 ${au.mainspring.nativeapp.TokenStore.calendarTimezone()}" else ""),
                    Modifier.padding(horizontal = 16.dp), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            items(state.jobs, key = { it.id }) { j ->
                au.mainspring.nativeapp.ui.ListCard({ onOpenJob(j.id) }, Modifier.padding(horizontal = 16.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(listOf(j.jobNumber, if(j.scheduledAt != null) bookingTime(j.scheduledAt) else null).filterNotNull().joinToString(" \u00b7 "), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            if(j.priority == "high" || j.priority == "urgent") au.mainspring.nativeapp.ui.StatusPill("urgent")
                            au.mainspring.nativeapp.ui.StatusPill(j.status)
                        }
                    }
                    Text(j.title, style = MaterialTheme.typography.titleMedium)
                    val vehicle = listOfNotNull(j.vehicleMake, j.vehicleModel, j.vehicleYear?.toString()).filter { it.isNotBlank() }.joinToString(" ")
                    val detail = listOf(vehicle, j.customerName.orEmpty()).filter { it.isNotBlank() }.joinToString(" \u00b7 ")
                    if(detail.isNotBlank()) Text(detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    j.jobAddress?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    if(state.day == null) j.scheduledAt?.let { Text(au.mainspring.nativeapp.ui.formatShopDate(it, au.mainspring.nativeapp.TokenStore.calendarTimezone()), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
            if(!state.loading && state.jobs.isEmpty() && state.error == null) item { au.mainspring.nativeapp.ui.EmptyState("No jobs match this view", "Try another filter or search.") }
            if(state.jobs.size < state.total) item { OutlinedButton(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) { Text("Load more jobs") } }
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
