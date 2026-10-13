package au.mainspring.nativeapp.ui.screens

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
    Scaffold(
        contentWindowInsets=if(embedded) WindowInsets(0,0,0,0) else ScaffoldDefaults.contentWindowInsets,
        topBar = {
            TopAppBar(
                windowInsets=if(embedded) WindowInsets(0,0,0,0) else TopAppBarDefaults.windowInsets,
                title = { Text(if(embedded) "Jobs" else "Mobile services", style = if(embedded) MaterialTheme.typography.titleMedium else MaterialTheme.typography.headlineSmall) },
                navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
            )
        },
    ) { padding ->
        LazyColumn(
            Modifier
                .padding(padding)
                .fillMaxSize(),
            contentPadding = PaddingValues(bottom = 24.dp),
        ) {
            item { Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            OutlinedTextField(state.query, viewModel::query, label = { Text("Search jobs, customers or registration") }, modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp), singleLine = true)
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("active", "completed", "all").forEach { value -> FilterChip(colors = androidx.compose.material3.FilterChipDefaults.filterChipColors(selectedContainerColor = MaterialTheme.colorScheme.onSurface, selectedLabelColor = MaterialTheme.colorScheme.surface), selected = state.directory == value && state.focus == null, onClick = { viewModel.directory(value) }, label = { Text(value.replaceFirstChar { it.uppercase() }) }) }
            }
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("today" to "Today", "unscheduled" to "Unscheduled", "unassigned" to "Unassigned", "needs_quote" to "Needs quote", "completed_unpaid" to "Completed, unpaid").forEach { (key, label) ->
                    FilterChip(colors = androidx.compose.material3.FilterChipDefaults.filterChipColors(selectedContainerColor = MaterialTheme.colorScheme.onSurface, selectedLabelColor = MaterialTheme.colorScheme.surface), selected = state.focus == key, onClick = { viewModel.focus(if(state.focus == key) null else key) }, label = { Text(label) })
                }
            }
            Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                Button(shape = MaterialTheme.shapes.small, onClick = onNewJob, enabled = au.mainspring.nativeapp.TokenStore.canWorkJobs()) { Text("New job") }
                Button(shape = MaterialTheme.shapes.small, onClick = { viewModel.refresh() }, enabled = !state.loading) { Text("Refresh") }
            }
            TextButton(onClick = { dateOpen = true }) { Text("Schedule by day") }
            state.day?.let { day ->
                Text(au.mainspring.nativeapp.ui.formatShopDate(day), style = MaterialTheme.typography.titleMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { viewModel.shiftDay(-1) }) { Text("Previous day") }
                    TextButton(onClick = { viewModel.shiftDay(1) }) { Text("Next day") }
                    TextButton(onClick = { viewModel.day(null) }) { Text("Clear date") }
                }
                Text("${state.jobs.size} of ${state.total} appointments loaded \u00b7 ${au.mainspring.nativeapp.TokenStore.calendarTimezone()}", style = MaterialTheme.typography.bodySmall)
            }
            if(state.loading && state.jobs.isNotEmpty()) androidx.compose.material3.LinearProgressIndicator(Modifier.fillMaxWidth())
            if (state.loading && state.jobs.isEmpty()) CircularProgressIndicator(Modifier.padding(24.dp))
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp)) }
            } }
                item {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(if(state.day != null) "APPOINTMENTS" else "JOBS", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("${state.jobs.size} of ${state.total}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                items(state.jobs, key = { it.id }) { j ->
                    Surface(color = MaterialTheme.colorScheme.surface) {
                        Row(
                            Modifier.fillMaxWidth().clickable { onOpenJob(j.id) }.padding(horizontal = 16.dp, vertical = 16.dp),
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            Column(Modifier.width(52.dp)) {
                                Text(bookingTime(j.scheduledAt), style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
                                Text(j.jobNumber, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
                            }
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(j.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                                val vehicle = listOfNotNull(j.vehicleMake, j.vehicleModel, j.vehicleYear?.toString()).filter { it.isNotBlank() }.joinToString(" ")
                                val detail = listOf(vehicle, j.customerName.orEmpty()).filter { it.isNotBlank() }.joinToString(" · ")
                                if(state.day == null) j.scheduledAt?.let { Text(au.mainspring.nativeapp.ui.formatShopDate(it, au.mainspring.nativeapp.TokenStore.calendarTimezone()), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                                if(detail.isNotBlank()) Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                j.jobAddress?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp)) {
                                        Text(au.mainspring.nativeapp.ui.statusLabel(j.status).replaceFirstChar { it.uppercase() }, modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp), style = MaterialTheme.typography.labelSmall)
                                    }
                                    if(j.priority == "high" || j.priority == "urgent") Text(j.priority.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 3.dp))
                                }
                            }
                        }
                    }
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                }
                if(!state.loading && state.jobs.isEmpty() && state.error == null) item { Text("No jobs match this view", modifier = Modifier.padding(16.dp)) }
                if(state.jobs.size < state.total) item { Button(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.padding(16.dp)) { Text("Load more jobs") } }
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
