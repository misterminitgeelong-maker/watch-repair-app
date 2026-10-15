package au.mainspring.nativeapp.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ConnectivityMonitor
import au.mainspring.nativeapp.RepairQueueViewModel
import au.mainspring.nativeapp.ShoeRepairQueueViewModel
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import au.mainspring.nativeapp.nextShoeQueueStatus
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.stateDescription
import au.mainspring.nativeapp.previewQueueSwipe
import au.mainspring.nativeapp.ui.*
import kotlinx.coroutines.launch

/** One card in the queue stack, lane-agnostic so watch and shoe jobs share the same UI. */
data class QueueCardUi(
    val id: String,
    val jobNumber: String,
    val title: String,
    val subtitle: String?,
    val customer: String?,
    val status: String,
    val due: String?,
    val description: String?,
    /** Status a right swipe produces, or null at the end of the lane. */
    val rightTarget: String?,
    /** Status a left swipe steps back to, or null when left means skip. */
    val leftTarget: String?,
)

/** Lane-agnostic view of a queue's state. */
data class QueueLaneUi(
    val loading: Boolean,
    val error: String?,
    val total: Int,
    val advanced: Int,
    val skipped: Int,
    val busy: Boolean,
    val canUndo: Boolean,
    val canAdvance: Boolean,
    val canGoBack: Boolean,
    val queue: List<QueueCardUi>,
    val emptyBody: String,
)

class QueueLaneActions(
    val refresh: () -> Unit, val dismissError: () -> Unit, val advance: () -> Unit, val backOrSkip: () -> Unit,
    val skip: () -> Unit, val undo: () -> Unit, val open: (String) -> Unit,
)

internal fun RepairJobRead.toCard() = QueueCardUi(
    id = id, jobNumber = jobNumber, title = title, subtitle = listOfNotNull(watchBrand, watchModel).joinToString(" ").ifBlank { null },
    customer = customerName, status = status, due = collectionDate, description = description,
    rightTarget = previewQueueSwipe(status, "right"), leftTarget = previewQueueSwipe(status, "left"),
)

internal fun ShoeRepairJobRead.toCard() = QueueCardUi(
    id = id, jobNumber = jobNumber, title = title,
    subtitle = items.map { it.name }.filter { it.isNotBlank() }.joinToString(", ").ifBlank { listOfNotNull(shoe?.brand, shoe?.shoeType).joinToString(" ").ifBlank { null } },
    customer = null, status = status, due = collectionDate, description = description,
    rightTarget = nextShoeQueueStatus(status), leftTarget = null,
)

/**
 * Repair queue swipe triage (web RepairQueueModal). Swipe the top card right to move the job
 * forward one status. On the watch lane left steps it back (or skips it when there is no earlier step);
 * on the shoe lane there is no back step, so left skips. Buttons do the same, and Undo reverses the last
 * action. A lane toggle switches between Watch and Shoe; the shoe lane is created lazily so it only
 * loads when selected. The watch lane is status-only; the shoe lane uses the normal shoe status endpoint.
 */
@Composable
fun RepairQueueScreen(
    onBack: () -> Unit,
    onOpenJob: (String) -> Unit,
    viewModel: RepairQueueViewModel = viewModel(),
    onOpenShoeJob: (String) -> Unit = {},
    initialLane: String = "watch",
    shoeViewModel: ShoeRepairQueueViewModel? = null,
) {
    var lane by rememberSaveable { mutableStateOf(initialLane) }
    val online by ConnectivityMonitor.online.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        BackLargeHeader("More", "Workshop", "Repair queue", onBack)
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            LaneChip("Watch", lane == "watch", Modifier.weight(1f).testTag("queue-lane-watch")) { lane = "watch" }
            LaneChip("Shoe", lane == "shoe", Modifier.weight(1f).testTag("queue-lane-shoe")) { lane = "shoe" }
        }
        if (!online) {
            Text("Offline. Moves are paused until you reconnect.", Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).testTag("queue-offline"),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
        if (lane == "shoe") {
            val vm = shoeViewModel ?: viewModel<ShoeRepairQueueViewModel>()
            val s by vm.state.collectAsStateWithLifecycle()
            val ui = QueueLaneUi(s.loading, s.error, s.total, s.advanced, s.skipped, s.busy, s.canUndo, s.canAdvance, false,
                s.queue.map { it.toCard() }, "Shoe repairs waiting on a step appear here.")
            QueueLane(ui, QueueLaneActions(vm::refresh, vm::dismissError, vm::advance, vm::backOrSkip, vm::skip, vm::undo, onOpenShoeJob))
        } else {
            val s by viewModel.state.collectAsStateWithLifecycle()
            val ui = QueueLaneUi(s.loading, s.error, s.total, s.advanced, s.skipped, s.busy, s.canUndo, s.canAdvance, s.canGoBack,
                s.queue.map { it.toCard() }, "Watch repairs waiting on a step appear here.")
            QueueLane(ui, QueueLaneActions(viewModel::refresh, viewModel::dismissError, viewModel::advance, viewModel::backOrSkip, viewModel::skip, viewModel::undo, onOpenJob))
        }
    }
}

@Composable private fun LaneChip(label: String, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    FilterChip(
        selected = selected, onClick = onClick, label = { Text(label, Modifier.fillMaxWidth(), textAlign = androidx.compose.ui.text.style.TextAlign.Center) },
        modifier = modifier.heightIn(min = 48.dp).semantics { role = Role.Button; stateDescription = if (selected) "Selected" else "Not selected" },
    )
}

@Composable private fun ColumnScope.QueueLane(s: QueueLaneUi, a: QueueLaneActions) {
    when {
        s.loading -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator(Modifier.testTag("queue-loading")) }
        s.error != null && s.total == 0 && s.queue.isEmpty() -> Column(Modifier.fillMaxWidth().padding(16.dp).testTag("queue-load-error"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(s.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            OutlinedButton(onClick = a.refresh, modifier = Modifier.heightIn(min = 48.dp).testTag("queue-retry")) { Text("Retry") }
        }
        s.total == 0 -> EmptyState("No jobs to triage", s.emptyBody, "Refresh", a.refresh, Modifier.testTag("queue-empty"))
        else -> {
            Progress(s.advanced, s.total, s.skipped)
            s.error?.let {
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp).testTag("queue-error"), verticalAlignment = Alignment.CenterVertically) {
                    Text(it, Modifier.weight(1f), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = a.dismissError, modifier = Modifier.heightIn(min = 48.dp)) { Text("Dismiss") }
                }
            }
            val current = s.queue.firstOrNull()
            if (current == null) {
                Column(Modifier.weight(1f).fillMaxWidth().testTag("queue-clear"), horizontalAlignment = Alignment.CenterHorizontally) {
                    EmptyState("Queue clear", "You moved ${s.advanced} job${if (s.advanced == 1) "" else "s"} along.", "Refresh", a.refresh)
                    TextButton(onClick = a.undo, enabled = s.canUndo, modifier = Modifier.heightIn(min = 48.dp).testTag("queue-undo")) { Text("Undo last") }
                }
            } else {
                Box(Modifier.weight(1f).fillMaxWidth().padding(16.dp)) {
                    s.queue.getOrNull(2)?.let { BackdropCard(2) }
                    s.queue.getOrNull(1)?.let { BackdropCard(1) }
                    SwipeCard(current, s.canAdvance, s.canGoBack, s.canUndo,
                        onSwipeRight = a.advance, onSwipeLeft = a.backOrSkip,
                        onSkip = a.skip, onUndo = a.undo, onOpen = { a.open(current.id) })
                }
                Controls(
                    current, s.busy, s.canAdvance, s.canGoBack, s.canUndo,
                    onAdvance = a.advance, onBackOrSkip = a.backOrSkip, onSkip = a.skip, onUndo = a.undo,
                )
            }
        }
    }
}

@Composable private fun Progress(advanced: Int, total: Int, skipped: Int) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        val text = "$advanced of $total moved" + if (skipped > 0) " · $skipped skipped" else ""
        if (LocalCalibre.current) MonoLabel(text, Modifier.testTag("queue-progress"))
        else Text(text, Modifier.testTag("queue-progress"), style = MaterialTheme.typography.labelLarge)
        LinearProgressIndicator(progress = { if (total == 0) 0f else advanced.toFloat() / total }, Modifier.fillMaxWidth())
    }
}

@Composable private fun BackdropCard(depth: Int) {
    val calibre = LocalCalibre.current
    Surface(
        Modifier.fillMaxWidth().fillMaxHeight(0.9f).padding(top = (depth * 10).dp, start = (depth * 6).dp, end = (depth * 6).dp),
        shape = if (calibre) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceVariant,
        border = if (calibre) BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant) else null,
    ) {}
}

@Composable private fun SwipeCard(
    job: QueueCardUi,
    canAdvance: Boolean,
    canGoBack: Boolean,
    canUndo: Boolean,
    onSwipeRight: () -> Unit,
    onSwipeLeft: () -> Unit,
    onSkip: () -> Unit,
    onUndo: () -> Unit,
    onOpen: () -> Unit,
) {
    val calibre = LocalCalibre.current
    val scope = rememberCoroutineScope()
    val threshold = with(LocalDensity.current) { 110.dp.toPx() }
    val offset = remember(job.id, job.status) { Animatable(0f) }
    val leftTarget = job.leftTarget
    val rightTarget = job.rightTarget
    val actions = buildList {
        if (canAdvance) add(CustomAccessibilityAction("Move to ${statusLabel(rightTarget.orEmpty())}") { onSwipeRight(); true })
        if (canGoBack) add(CustomAccessibilityAction("Send back to ${statusLabel(leftTarget.orEmpty())}") { onSwipeLeft(); true })
        add(CustomAccessibilityAction("Skip to end of queue") { onSkip(); true })
        if (canUndo) add(CustomAccessibilityAction("Undo last action") { onUndo(); true })
    }
    Surface(
        Modifier.fillMaxWidth().fillMaxHeight(0.9f)
            .graphicsLayer { translationX = offset.value; rotationZ = offset.value / 60f }
            .semantics(mergeDescendants = true) { customActions = actions }
            .pointerInput(job.id, job.status, canAdvance, canGoBack) {
                detectHorizontalDragGestures(
                    onDragEnd = {
                        val x = offset.value
                        scope.launch {
                            if (x > threshold && canAdvance) onSwipeRight()
                            else if (x < -threshold) onSwipeLeft()
                            offset.animateTo(0f)
                        }
                    },
                    onDragCancel = { scope.launch { offset.animateTo(0f) } },
                ) { change, drag -> change.consume(); scope.launch { offset.snapTo(offset.value + drag) } }
            }
            .clickable(onClick = onOpen)
            .testTag("queue-card"),
        shape = if (calibre) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        shadowElevation = if (calibre) 0.dp else 4.dp,
    ) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (calibre) MonoLabel(job.jobNumber) else Text(job.jobNumber, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(job.title, style = MaterialTheme.typography.headlineSmall)
            job.subtitle?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
            job.customer?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            StatusPill(job.status, Modifier.testTag("queue-status"))
            job.due?.takeIf { it.isNotBlank() }?.let { Text("Due $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            job.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 6) }
            Spacer(Modifier.weight(1f))
            Text(
                "Swipe right: " + (rightTarget?.let { statusLabel(it) } ?: "final step") + "  ·  Swipe left: " + (leftTarget?.let { "back to ${statusLabel(it)}" } ?: "skip"),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable private fun Controls(
    job: QueueCardUi,
    busy: Boolean,
    canAdvance: Boolean,
    canGoBack: Boolean,
    canUndo: Boolean,
    onAdvance: () -> Unit,
    onBackOrSkip: () -> Unit,
    onSkip: () -> Unit,
    onUndo: () -> Unit,
) {
    Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onBackOrSkip, enabled = !busy && canGoBack, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-back")) { Text("Back") }
            OutlinedButton(onClick = onSkip, enabled = !busy, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-skip")) { Text("Skip") }
            OutlinedButton(onClick = onUndo, enabled = canUndo, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-undo")) { Text("Undo") }
        }
        val next = job.rightTarget
        Button(onClick = onAdvance, enabled = canAdvance, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("queue-advance")) {
            Text(if (busy) "Saving..." else next?.let { "Move to ${statusLabel(it)}" } ?: "Final step")
        }
    }
}
