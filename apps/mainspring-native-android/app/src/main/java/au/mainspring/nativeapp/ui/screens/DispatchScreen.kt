package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
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
) {
    val state by model.state.collectAsStateWithLifecycle()
    RefreshOnResume(model::refresh)
    val zone = runCatching { ZoneId.of(TokenStore.calendarTimezone()) }.getOrDefault(ZoneId.systemDefault())
    val time = DateTimeFormatter.ofPattern("h:mm a", Locale.forLanguageTag("en-AU"))
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { LargeHeader("Mobile services · Today", "Dispatch", onAdd = if(TokenStore.canWorkJobs()) onNew else null, addDescription = "New job") }
        item { RouteArt(Modifier.padding(horizontal = 20.dp), onOpenRoute) }
        item {
            SegmentedPills(listOf("today" to "Today", "week" to "This week", "pool" to "Pool"), "today",
                { key -> when(key) { "week" -> onOpenPlanner(); "pool" -> onOpenPool(); else -> Unit } }, Modifier.padding(horizontal = 20.dp))
        }
        item {
            Row(Modifier.fillMaxWidth().padding(horizontal = 24.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Next on the road", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                TextButton(onClick = onOpenPlanner, modifier = Modifier.heightIn(min = 44.dp)) { Text("Planner", style = MaterialTheme.typography.labelLarge) }
            }
        }
        if(state.loading && state.jobs.isEmpty()) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        state.error?.let { item { ErrorBanner(it, Modifier.padding(horizontal = 20.dp), onRetry = model::refresh) } }
        if(!state.loading && state.error == null && state.jobs.isEmpty()) item { EmptyState("No appointments today", "Check the pool for nearby work, or plan the week.") }
        items(state.jobs, key = { it.id }) { job ->
            val whenText = bookingInstant(job.scheduledAt)?.atZone(zone)?.format(time)
            ListCard({ onOpenJob(job.id) }, Modifier.padding(horizontal = 20.dp)) {
                Text(listOfNotNull(listOfNotNull(job.vehicleMake, job.vehicleModel).joinToString(" ").takeIf { it.isNotBlank() }, job.title).joinToString(" · "), style = MaterialTheme.typography.titleMedium, maxLines = 1)
                Text(listOfNotNull(whenText, job.jobAddress?.takeIf { it.isNotBlank() }, job.customerName).joinToString(" · "), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                Text(statusLabel(job.status) + if(job.priority == "urgent") " · Urgent" else "", style = MaterialTheme.typography.labelMedium,
                    color = if(job.priority == "urgent") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
            }
        }
        item {
            PrimaryAction(onClick = onOpenPool, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).heightIn(min = 52.dp)) { Text("Open available job pool", style = MaterialTheme.typography.titleMedium) }
        }
    }
}

/** Stylised route card (roads, water, dotted route) standing in for the live map. Tap opens today's route list. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RouteArt(modifier: Modifier, onClick: () -> Unit) {
    Surface(onClick, modifier.fillMaxWidth().height(210.dp), shape = MaterialTheme.shapes.medium, color = Color(0xFFE5E9DD)) {
        Canvas(Modifier.fillMaxSize()) {
            val u = size.width / 354f
            drawRoundRect(Color(0xFFC9DCE4), Offset(size.width * 0.72f, 0f), Size(size.width * 0.28f, size.height), CornerRadius(60f * u))
            val road = Color.White
            fun r(x1: Float, y1: Float, x2: Float, y2: Float, w: Float = 13f) = drawLine(road, Offset(x1 * u, y1 * u), Offset(x2 * u, y2 * u), w * u)
            r(0f, 60f, 354f, 20f); r(0f, 130f, 300f, 80f); r(60f, 0f, 20f, 210f); r(140f, 0f, 190f, 210f, 15f); r(250f, 0f, 220f, 210f, 10f)
            val path = Path().apply { moveTo(75f * u, 160f * u); cubicTo(110f * u, 90f * u, 140f * u, 60f * u, 170f * u, 70f * u); cubicTo(210f * u, 85f * u, 230f * u, 50f * u, 236f * u, 52f * u) }
            drawPath(path, Color(0xFF2453D4), style = Stroke(5f * u, pathEffect = PathEffect.dashPathEffect(floatArrayOf(14f * u, 9f * u))))
            drawCircle(Color(0xFF17202C), 9f * u, Offset(75f * u, 160f * u)); drawCircle(Color(0xFF2453D4), 10f * u, Offset(140f * u, 72f * u)); drawCircle(Color(0xFF16734F), 10f * u, Offset(236f * u, 52f * u))
        }
    }
}
