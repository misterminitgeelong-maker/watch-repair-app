package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.TodayViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.bookingInstant
import au.mainspring.nativeapp.ui.*
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Atelier "Dispatch": route illustration, Today / This week / Pool pills and "Next on the road". */
@Composable
fun DispatchScreen(
    onOpenJob: (String) -> Unit,
    onNew: () -> Unit,
    onOpenRoute: () -> Unit,
    onOpenPlanner: () -> Unit,
    onOpenPool: () -> Unit,
    model: TodayViewModel = viewModel(),
    extras: au.mainspring.nativeapp.DispatchExtrasViewModel = viewModel(),
) {
    val state by model.state.collectAsStateWithLifecycle()
    val extra by extras.state.collectAsStateWithLifecycle()
    var lane by rememberSaveable { mutableStateOf("all") }
    var riskFirst by rememberSaveable { mutableStateOf(false) }
    var confirmReminders by rememberSaveable { mutableStateOf(false) }
    val now = java.time.Instant.now()
    val shown = state.jobs.filter { lane == "all" || (lane == "none" && it.assignedUserId == null) || it.assignedUserId == lane }
        .let { rows -> if(riskFirst) rows.sortedWith(compareByDescending<au.mainspring.nativeapp.api.AutoKeyJobRead> { au.mainspring.nativeapp.slaChip(it, now)?.weight ?: 0 }.then(au.mainspring.nativeapp.DispatchSlaOrder)) else rows.sortedWith(au.mainspring.nativeapp.DispatchSlaOrder) }
    RefreshOnResume(model::refresh)
    val zone = runCatching { ZoneId.of(TokenStore.calendarTimezone()) }.getOrDefault(ZoneId.systemDefault())
    val time = DateTimeFormatter.ofPattern("h:mm a", Locale.forLanguageTag("en-AU"))
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { LargeHeader("Mobile services · Today", "Dispatch", onAdd = if(TokenStore.canWorkJobs()) onNew else null, addDescription = "New job") }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                RouteArt(Modifier, onOpenRoute)
                if(LocalCalibre.current) MonoLabel("Illustrative area diagram")
            }
        }
        item {
            SegmentedPills(listOf("today" to "Today", "week" to "This week", "pool" to "Pool"), "today",
                { key -> when(key) { "week" -> onOpenPlanner(); "pool" -> onOpenPool(); else -> Unit } }, Modifier.padding(horizontal = 20.dp))
        }
        item {
            if(LocalCalibre.current) Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { MonoLabel("Today"); Text("Next on the road", style = MaterialTheme.typography.titleLarge) }
                LinkAction(onClick = onOpenPlanner) { Text("Planner", style = MaterialTheme.typography.labelLarge) }
            } else Row(Modifier.fillMaxWidth().padding(horizontal = 24.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Next on the road", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                TextButton(onClick = onOpenPlanner, modifier = Modifier.heightIn(min = 44.dp)) { Text("Planner", style = MaterialTheme.typography.labelLarge) }
            }
        }
        if(extra.technicians.isNotEmpty() || riskFirst || state.jobs.any { it.assignedUserId == null }) item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    PillChip("All lanes", lane == "all", { lane = "all" })
                    extra.technicians.forEach { t -> PillChip(t.name, lane == t.id, { lane = t.id }) }
                    PillChip("Unassigned", lane == "none", { lane = "none" })
                    PillChip(if(riskFirst) "Risk first: on" else "Risk first", riskFirst, { riskFirst = !riskFirst })
                }
            }
        }
        if(state.loading && state.jobs.isEmpty()) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        state.error?.let { item { ErrorBanner(it, Modifier.padding(horizontal = 20.dp), onRetry = model::refresh) } }
        if(!state.loading && state.error == null && shown.isEmpty()) item { EmptyState(if(state.jobs.isEmpty()) "No appointments today" else "Nothing in this lane", if(state.jobs.isEmpty()) "Check the pool for nearby work, or plan the week." else "Pick another lane to see the rest of today.") }
        items(shown, key = { it.id }) { job ->
            val whenText = bookingInstant(job.scheduledAt)?.atZone(zone)?.format(time)
            val sla = au.mainspring.nativeapp.slaChip(job, now)
            if(LocalCalibre.current) {
                CalibreRow({ onOpenJob(job.id) },
                    listOfNotNull(listOfNotNull(job.vehicleMake, job.vehicleModel).joinToString(" ").takeIf { it.isNotBlank() }, job.title).joinToString(" · "),
                    listOfNotNull(whenText, job.jobAddress?.takeIf { it.isNotBlank() }, job.customerName).joinToString(" · "),
                    statusLabel(job.status) + (if(job.priority == "urgent") " · Urgent" else "") + (sla?.let { " · ${it.label}" } ?: ""), job.priority == "urgent" || sla == au.mainspring.nativeapp.SlaKind.LATE, Modifier.padding(horizontal = 20.dp))
                return@items
            }
            ListCard({ onOpenJob(job.id) }, Modifier.padding(horizontal = 20.dp)) {
                Text(listOfNotNull(listOfNotNull(job.vehicleMake, job.vehicleModel).joinToString(" ").takeIf { it.isNotBlank() }, job.title).joinToString(" · "), style = MaterialTheme.typography.titleMedium, maxLines = 1)
                Text(listOfNotNull(whenText, job.jobAddress?.takeIf { it.isNotBlank() }, job.customerName).joinToString(" · "), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(statusLabel(job.status) + if(job.priority == "urgent") " · Urgent" else "", style = MaterialTheme.typography.labelMedium,
                        color = if(job.priority == "urgent") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                    sla?.let { SlaChip(it) }
                }
            }
        }
        if(TokenStore.canWorkJobs()) item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                extra.message?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                extra.error?.let { ErrorBanner(it) }
                if(extra.uncertain) LinkAction(onClick = extras::acknowledgeUncertain) { Text("I have checked, allow another send") }
                else LinkAction(onClick = { confirmReminders = true }, enabled = !extra.busy) { Text(if(extra.busy) "Sending reminders…" else "Send tomorrow's reminders") }
            }
        }
        item {
            PrimaryAction(onClick = onOpenPool, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).heightIn(min = 52.dp)) { Text("Open available job pool", style = MaterialTheme.typography.titleMedium) }
        }
    }
    if(confirmReminders) ReminderConfirm(onConfirm = { confirmReminders = false; extras.sendReminders() }, onDismiss = { confirmReminders = false })
}

@Composable private fun ReminderConfirm(onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Text tomorrow's customers?") },
        text = { Text("Sends a reminder SMS to every customer with an open booking tomorrow. Customers who were already reminded will be texted again.") },
        confirmButton = { TextButton(onClick = onConfirm) { Text("Send reminders") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } })
}

/** Calibre secondary action: a plain text link with a trailing arrow. Outside Calibre it is the regular outlined button. */
@Composable internal fun LinkAction(onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true,
    shape: androidx.compose.ui.graphics.Shape = MaterialTheme.shapes.small, contentPadding: PaddingValues = ButtonDefaults.ContentPadding,
    content: @Composable RowScope.() -> Unit) {
    if(LocalCalibre.current) {
        TextButton(onClick, modifier.heightIn(min = 44.dp), enabled, contentPadding = PaddingValues(horizontal = 0.dp, vertical = 8.dp)) {
            content(); Spacer(Modifier.width(6.dp)); Text("→")
        }
        return
    }
    SecondaryAction(onClick, modifier, enabled, shape, contentPadding = contentPadding, content = content)
}

/** Atelier card (as before) or, in Calibre, a flat hairline panel; with [onClick] a flat tappable row. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun CardOrFlat(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, padding: androidx.compose.ui.unit.Dp = 12.dp, spacing: androidx.compose.ui.unit.Dp = 6.dp,
    content: @Composable ColumnScope.() -> Unit) {
    if(LocalCalibre.current) { if(onClick != null) ListCard(onClick, modifier, content) else FlatPanel(modifier, content); return }
    val inner: @Composable () -> Unit = { Column(Modifier.padding(padding), verticalArrangement = Arrangement.spacedBy(spacing), content = content) }
    if(onClick != null) Card(onClick, modifier.fillMaxWidth()) { inner() } else Card(modifier.fillMaxWidth()) { inner() }
}

/** Calibre list row: title with arrow, mono reference line, status dot line, hairline below (the HubJobCard pattern). */
@Composable internal fun CalibreRow(onClick: () -> Unit, title: String, reference: String?, status: String?, urgent: Boolean = false, modifier: Modifier = Modifier) {
    ListCard(onClick, modifier) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, maxLines = 1)
            Text("›", style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.onSurface)
        }
        if(!reference.isNullOrBlank()) MonoLabel(reference)
        if(!status.isNullOrBlank()) {
            val tone = if(urgent) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Box(Modifier.size(6.dp).background(tone, androidx.compose.foundation.shape.CircleShape))
                Text(status, style = MaterialTheme.typography.labelMedium, color = tone)
            }
        }
    }
}

/** Stylised route card (roads, water, dotted route) standing in for the live map. Tap opens today's route list. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RouteArt(modifier: Modifier, onClick: () -> Unit) {
    val calibre = LocalCalibre.current
    Surface(onClick, modifier.fillMaxWidth().height(210.dp).semantics { contentDescription = "Open today's route" }, shape = if(calibre) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.medium, color = if(calibre) Calibre.Grey else Color(0xFFE5E9DD)) {
        Canvas(Modifier.fillMaxSize()) {
            val u = size.width / 354f
            if(!calibre) drawRoundRect(Color(0xFFC9DCE4), Offset(size.width * 0.72f, 0f), Size(size.width * 0.28f, size.height), CornerRadius(60f * u))
            val road = Color.White
            fun r(x1: Float, y1: Float, x2: Float, y2: Float, w: Float = 13f) = drawLine(road, Offset(x1 * u, y1 * u), Offset(x2 * u, y2 * u), w * u)
            r(0f, 60f, 354f, 20f); r(0f, 130f, 300f, 80f); r(60f, 0f, 20f, 210f); r(140f, 0f, 190f, 210f, 15f); r(250f, 0f, 220f, 210f, 10f)
            val path = Path().apply { moveTo(75f * u, 160f * u); cubicTo(110f * u, 90f * u, 140f * u, 60f * u, 170f * u, 70f * u); cubicTo(210f * u, 85f * u, 230f * u, 50f * u, 236f * u, 52f * u) }
            drawPath(path, if(calibre) Calibre.Forest else Color(0xFF2453D4), style = Stroke(5f * u, pathEffect = PathEffect.dashPathEffect(floatArrayOf(14f * u, 9f * u))))
            drawCircle(Color(0xFF17202C), 9f * u, Offset(75f * u, 160f * u)); drawCircle(if(calibre) Calibre.Forest else Color(0xFF2453D4), 10f * u, Offset(140f * u, 72f * u)); drawCircle(if(calibre) Color(0xFF17202C) else Color(0xFF16734F), 10f * u, Offset(236f * u, 52f * u))
        }
    }
}
