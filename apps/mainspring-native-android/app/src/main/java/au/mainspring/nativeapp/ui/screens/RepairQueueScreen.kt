package au.mainspring.nativeapp.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ConnectivityMonitor
import au.mainspring.nativeapp.QUEUE_ADVANCE_NOTE_CHIPS
import au.mainspring.nativeapp.QUEUE_FILTER_STATUSES
import au.mainspring.nativeapp.QUEUE_NO_UPDATE_CHIPS
import au.mainspring.nativeapp.QUEUE_PRIORITIES
import au.mainspring.nativeapp.QUEUE_RECOMMENDED_ACTION
import au.mainspring.nativeapp.QUEUE_SMS_REMIND_STATUSES
import au.mainspring.nativeapp.QUEUE_STATUS_NOTE_CHIPS
import au.mainspring.nativeapp.QueueFilters
import au.mainspring.nativeapp.QueueUiState
import au.mainspring.nativeapp.QueueWorkLogs
import au.mainspring.nativeapp.RepairQueueViewModel
import au.mainspring.nativeapp.ShoeRepairQueueViewModel
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.ShoeJobItemRead
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import au.mainspring.nativeapp.collectionUrgency
import au.mainspring.nativeapp.daysInShop
import au.mainspring.nativeapp.nextShoeQueueStatus
import au.mainspring.nativeapp.previewQueueSwipe
import au.mainspring.nativeapp.toggled
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
    val priority: String = "normal",
    /** 0 overdue, 1 due today, 2 due tomorrow, 3 otherwise. */
    val urgency: Int = 3,
    val daysInShop: Int = 0,
    val claimedByName: String? = null,
    val claimedMine: Boolean = false,
    val claimedOther: Boolean = false,
)

/** Lane-agnostic view of a queue's state. */
data class QueueLaneUi(
    val loading: Boolean,
    val error: String?,
    val notice: String?,
    val total: Int,
    val done: Int,
    val advanced: Int,
    val checkedIn: Int,
    val skipped: Int,
    val busy: Boolean,
    val canUndo: Boolean,
    val canAdvance: Boolean,
    val canGoBack: Boolean,
    val queue: List<QueueCardUi>,
    val emptyBody: String,
    val filters: QueueFilters,
    /** The watch lane shows work log history and a Log work action. */
    val workLogs: QueueWorkLogs? = null,
    /** The shoe lane can text the customer a reminder (the web offers that on the shoe lane only). */
    val showSms: Boolean = false,
    val canReset: Boolean = false,
)

class QueueLaneActions(
    val refresh: () -> Unit, val dismissError: () -> Unit, val advance: (String?) -> Unit, val backOrSkip: () -> Unit,
    val skip: () -> Unit, val undo: () -> Unit, val open: (String) -> Unit,
    val noUpdate: (String?) -> Unit, val saveNote: (String) -> Unit, val toggleClaim: () -> Unit,
    val logWork: (String, Int?) -> Unit, val sendSms: () -> Unit, val setFilters: (QueueFilters) -> Unit, val resetDay: () -> Unit,
)

private fun claimFields(claimedUserId: String?, claimedName: String?, me: String) =
    Triple(claimedName, claimedUserId != null && claimedUserId == me, claimedUserId != null && claimedUserId != me)

internal fun RepairJobRead.toCard(me: String = "") = claimFields(claimedByUserId, claimedByName, me).let { (name, mine, other) ->
    QueueCardUi(
        id = id, jobNumber = jobNumber, title = title, subtitle = listOfNotNull(watchBrand, watchModel).joinToString(" ").ifBlank { null },
        customer = customerName, status = status, due = collectionDate, description = description,
        rightTarget = previewQueueSwipe(status, "right"), leftTarget = previewQueueSwipe(status, "left"),
        priority = priority, urgency = collectionUrgency(collectionDate), daysInShop = daysInShop(createdAt),
        claimedByName = name, claimedMine = mine, claimedOther = other,
    )
}

internal fun ShoeRepairJobRead.toCard(me: String = "") = claimFields(claimedByUserId, claimedByName, me).let { (name, mine, other) ->
    QueueCardUi(
        id = id, jobNumber = jobNumber, title = title,
        subtitle = (items as List<ShoeJobItemRead>?).orEmpty().map { it.name }.filter { it.isNotBlank() }.joinToString(", ").ifBlank { listOfNotNull(shoe?.brand, shoe?.shoeType).joinToString(" ").ifBlank { null } },
        customer = null, status = status, due = collectionDate, description = description,
        rightTarget = nextShoeQueueStatus(status), leftTarget = null,
        priority = priority, urgency = collectionUrgency(collectionDate), daysInShop = daysInShop(createdAt),
        claimedByName = name, claimedMine = mine, claimedOther = other,
    )
}

private fun <J : Any> QueueUiState<J>.toLane(empty: String, workLogs: QueueWorkLogs?, showSms: Boolean, card: (J) -> QueueCardUi) = QueueLaneUi(
    loading = loading, error = error, notice = notice, total = total, done = doneCount, advanced = advanced, checkedIn = checkedIn, skipped = skipped,
    busy = busy, canUndo = canUndo, canAdvance = canAdvance, canGoBack = canGoBack, queue = queue.map(card), emptyBody = empty, filters = filters,
    workLogs = workLogs, showSms = showSms, canReset = doneCount > 0 || skipped > 0 || checkedIn > 0,
)

/**
 * Repair queue swipe triage (web RepairQueueModal). Swipe the top card right to move the job
 * forward one status. On the watch lane left steps it back (or skips it when there is no earlier step);
 * on the shoe lane there is no back step, so left skips. Buttons do the same, and Undo reverses the last
 * action. Cards can take a note, log work (watch), be claimed, marked "no update" or, on the shoe lane, send an SMS
 * reminder. Filters narrow the queue, and the day's progress is saved to the server so it syncs with the web.
 * A lane toggle switches between Watch and Shoe; the shoe lane is created lazily so it only loads when selected.
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
            val ui = s.toLane("Shoe repairs waiting on a step appear here.", null, true) { it.toCard(vm.userId) }
            QueueLane(ui, QueueLaneActions(vm::refresh, vm::dismissError, vm::advance, vm::backOrSkip, vm::skip, vm::undo, onOpenShoeJob,
                vm::noUpdate, vm::saveNote, vm::toggleClaim, { _, _ -> }, vm::sendReminder, vm::setFilters, vm::resetDay))
        } else {
            val s by viewModel.state.collectAsStateWithLifecycle()
            val logs by viewModel.workLogs.collectAsStateWithLifecycle()
            val ui = s.toLane("Watch repairs waiting on a step appear here.", logs, false) { it.toCard(viewModel.userId) }
            QueueLane(ui, QueueLaneActions(viewModel::refresh, viewModel::dismissError, viewModel::advance, viewModel::backOrSkip, viewModel::skip, viewModel::undo, onOpenJob,
                viewModel::noUpdate, viewModel::saveNote, viewModel::toggleClaim, viewModel::logWork, {}, viewModel::setFilters, viewModel::resetDay))
        }
    }
}

@Composable private fun LaneChip(label: String, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    FilterChip(
        selected = selected, onClick = onClick, label = { Text(label, Modifier.fillMaxWidth(), textAlign = TextAlign.Center) },
        modifier = modifier.heightIn(min = 48.dp).semantics { role = Role.Button; stateDescription = if (selected) "Selected" else "Not selected" },
    )
}

/** Which note or log panel is open over the queue. */
private enum class QueuePanel { Note, NoUpdate, MoveWithNote, LogWork, ResetDay }

@Composable private fun ColumnScope.QueueLane(s: QueueLaneUi, a: QueueLaneActions) {
    var panel by rememberSaveable { mutableStateOf<QueuePanel?>(null) }
    var showFilters by rememberSaveable { mutableStateOf(false) }
    when {
        s.loading -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator(Modifier.testTag("queue-loading")) }
        s.error != null && s.total == 0 && s.queue.isEmpty() && !s.filters.active -> Column(Modifier.fillMaxWidth().padding(16.dp).testTag("queue-load-error"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(s.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
            OutlinedButton(onClick = a.refresh, modifier = Modifier.heightIn(min = 48.dp).testTag("queue-retry")) { Text("Retry") }
        }
        s.total == 0 && !s.filters.active -> EmptyState("No jobs to triage", s.emptyBody, "Refresh", a.refresh, Modifier.testTag("queue-empty"))
        else -> {
            Progress(s, showFilters, onToggleFilters = { showFilters = !showFilters }, onReset = { panel = QueuePanel.ResetDay })
            if (showFilters) FilterPanel(s.filters, a.setFilters)
            s.error?.let {
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp).testTag("queue-error"), verticalAlignment = Alignment.CenterVertically) {
                    Text(it, Modifier.weight(1f), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = a.dismissError, modifier = Modifier.heightIn(min = 48.dp)) { Text("Dismiss") }
                }
            }
            s.notice?.let {
                Text(it, Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 2.dp).testTag("queue-notice"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
            }
            val current = s.queue.firstOrNull()
            if (current == null) {
                Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).testTag("queue-clear"), horizontalAlignment = Alignment.CenterHorizontally) {
                    if (s.filters.active && s.done == 0) EmptyState("No jobs match", "No waiting job matches the filters.", "Clear filters", { a.setFilters(QueueFilters()) })
                    else {
                        EmptyState("Queue clear", "You cleared ${s.done} job${if (s.done == 1) "" else "s"} today.", "Refresh", a.refresh)
                        DaySummary(s)
                    }
                    TextButton(onClick = a.undo, enabled = s.canUndo, modifier = Modifier.heightIn(min = 48.dp).testTag("queue-undo")) { Text("Undo last") }
                }
            } else {
                Box(Modifier.weight(1f).fillMaxWidth().padding(16.dp)) {
                    s.queue.getOrNull(2)?.let { BackdropCard(2) }
                    s.queue.getOrNull(1)?.let { BackdropCard(1) }
                    SwipeCard(current, s, s.canAdvance, s.canGoBack, s.canUndo, a,
                        onNote = { panel = QueuePanel.Note }, onLogWork = { panel = QueuePanel.LogWork },
                        onSwipeRight = { a.advance(null) }, onSwipeLeft = a.backOrSkip,
                        onSkip = a.skip, onUndo = a.undo, onOpen = { a.open(current.id) })
                }
                Controls(
                    current, s.busy, s.canAdvance, s.canGoBack, s.canUndo,
                    onAdvance = { a.advance(null) }, onBackOrSkip = a.backOrSkip, onSkip = a.skip, onUndo = a.undo,
                    onNoUpdate = { panel = QueuePanel.NoUpdate }, onMoveWithNote = { panel = QueuePanel.MoveWithNote },
                )
            }
            val card = current
            when (panel) {
                QueuePanel.Note -> if (card != null) NoteDialog("Add a note", "Status unchanged", QUEUE_STATUS_NOTE_CHIPS[card.status].orEmpty(), "Save note", true, { panel = null }) { a.saveNote(it ?: ""); panel = null }
                QueuePanel.NoUpdate -> if (card != null) NoteDialog("No update", "Mark checked in; the job stays where it is for today", QUEUE_NO_UPDATE_CHIPS[card.status].orEmpty(), "Checked in", false, { panel = null }) { a.noUpdate(it); panel = null }
                QueuePanel.MoveWithNote -> if (card?.rightTarget != null) NoteDialog("Move to ${statusLabel(card.rightTarget)}", "Add a note (optional)", QUEUE_ADVANCE_NOTE_CHIPS[card.rightTarget].orEmpty(), "Move", false, { panel = null }) { a.advance(it); panel = null }
                QueuePanel.LogWork -> LogWorkDialog({ panel = null }) { note, minutes -> a.logWork(note, minutes); panel = null }
                QueuePanel.ResetDay -> AlertDialog(
                    onDismissRequest = { panel = null },
                    title = { Text("Reset today's progress?") },
                    text = { Text("Clear today's saved queue progress. Jobs you already cleared will show again.") },
                    confirmButton = { TextButton({ a.resetDay(); panel = null }, Modifier.heightIn(min = 48.dp).testTag("queue-reset-confirm")) { Text("Reset") } },
                    dismissButton = { TextButton({ panel = null }, Modifier.heightIn(min = 48.dp)) { Text("Cancel") } },
                )
                null -> {}
            }
        }
    }
}

@Composable private fun Progress(s: QueueLaneUi, filtersOpen: Boolean, onToggleFilters: () -> Unit, onReset: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        val remaining = (s.total - s.done).coerceAtLeast(0)
        val text = "${s.done} done · $remaining left" + (if (s.skipped > 0) " · ${s.skipped} skipped" else "")
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1f)) {
                if (LocalCalibre.current) MonoLabel(text, Modifier.testTag("queue-progress"))
                else Text(text, Modifier.testTag("queue-progress"), style = MaterialTheme.typography.labelLarge)
            }
            val filterLabel = if (s.filters.count > 0) "${s.filters.count} filter${if (s.filters.count > 1) "s" else ""}" else "Filter"
            if (filtersOpen || s.filters.active) {
                FilledTonalButton(onClick = onToggleFilters, modifier = Modifier.heightIn(min = 48.dp).testTag("queue-filter")) { Text(filterLabel) }
            } else OutlinedButton(onClick = onToggleFilters, modifier = Modifier.heightIn(min = 48.dp).testTag("queue-filter")) { Text(filterLabel) }
            if (s.canReset) TextButton(onClick = onReset, enabled = !s.busy, modifier = Modifier.heightIn(min = 48.dp).testTag("queue-reset-day")) { Text("Reset day") }
        }
        LinearProgressIndicator(progress = { if (s.total == 0) 0f else (s.done.toFloat() / s.total).coerceIn(0f, 1f) }, Modifier.fillMaxWidth())
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable private fun FilterPanel(f: QueueFilters, onChange: (QueueFilters) -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).testTag("queue-filter-panel"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Status", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            QUEUE_FILTER_STATUSES.forEach { st ->
                FilterChip(f.statuses.contains(st), { onChange(f.copy(statuses = f.statuses.toggled(st))) }, { Text(statusLabel(st)) },
                    Modifier.heightIn(min = 48.dp).testTag("queue-filter-status-$st"))
            }
        }
        Text("Priority", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            QUEUE_PRIORITIES.forEach { p ->
                FilterChip(f.priorities.contains(p), { onChange(f.copy(priorities = f.priorities.toggled(p))) }, { Text(p.replaceFirstChar { it.uppercase() }) },
                    Modifier.heightIn(min = 48.dp).testTag("queue-filter-priority-$p"))
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(f.dueTodayOnly, { onChange(f.copy(dueTodayOnly = !f.dueTodayOnly)) }, { Text("Due today / overdue only") }, Modifier.heightIn(min = 48.dp).testTag("queue-filter-due"))
            if (f.active) TextButton({ onChange(QueueFilters()) }, Modifier.heightIn(min = 48.dp).testTag("queue-filter-clear")) { Text("Clear all") }
        }
    }
}

@Composable private fun DaySummary(s: QueueLaneUi) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp).testTag("queue-summary"), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf("Advanced" to s.advanced, "Checked in" to s.checkedIn, "Skipped" to s.skipped).forEach { (label, count) ->
            OutlinedCard(Modifier.weight(1f)) {
                Column(Modifier.fillMaxWidth().padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("$count", style = MaterialTheme.typography.headlineSmall)
                    Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
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

private fun priorityColor(priority: String): Color = when (priority) {
    "urgent" -> Color(0xFFC0392B)
    "high" -> Color(0xFFD4693A)
    "low" -> Color(0xFF8A7563)
    else -> Color(0xFF7A5D2E)
}

@Composable private fun Badge(text: String, color: Color, modifier: Modifier = Modifier) {
    Text(text, modifier.background6(color).padding(horizontal = 6.dp, vertical = 2.dp), style = MaterialTheme.typography.labelSmall, color = Color.White, maxLines = 1)
}

private fun Modifier.background6(color: Color): Modifier = this.then(Modifier.background(color, RoundedCornerShape(4.dp)))

@Composable private fun SwipeCard(
    job: QueueCardUi,
    lane: QueueLaneUi,
    canAdvance: Boolean,
    canGoBack: Boolean,
    canUndo: Boolean,
    actions: QueueLaneActions,
    onNote: () -> Unit,
    onLogWork: () -> Unit,
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
    val acts = buildList {
        if (canAdvance) add(CustomAccessibilityAction("Move to ${statusLabel(rightTarget.orEmpty())}") { onSwipeRight(); true })
        if (canGoBack) add(CustomAccessibilityAction("Send back to ${statusLabel(leftTarget.orEmpty())}") { onSwipeLeft(); true })
        add(CustomAccessibilityAction("Skip to end of queue") { onSkip(); true })
        if (canUndo) add(CustomAccessibilityAction("Undo last action") { onUndo(); true })
    }
    Surface(
        Modifier.fillMaxWidth().fillMaxHeight(0.9f)
            .graphicsLayer { translationX = offset.value; rotationZ = offset.value / 60f }
            .semantics(mergeDescendants = true) { customActions = acts }
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
        Column(Modifier.verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(Modifier.weight(1f)) {
                    if (calibre) MonoLabel(job.jobNumber) else Text(job.jobNumber, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Badge(job.priority.uppercase(), priorityColor(job.priority), Modifier.testTag("queue-priority"))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(if (job.daysInShop == 0) "Today" else if (job.daysInShop == 1) "1 day in shop" else "${job.daysInShop} days in shop",
                    style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                when (job.urgency) {
                    0 -> Badge("OVERDUE", Color(0xFF7B241C), Modifier.testTag("queue-urgency"))
                    1 -> Badge("DUE TODAY", Color(0xFFC0392B), Modifier.testTag("queue-urgency"))
                    2 -> Badge("DUE TOMORROW", Color(0xFFD4693A), Modifier.testTag("queue-urgency"))
                }
                if (job.claimedMine) Badge("ON IT", MaterialTheme.colorScheme.primary, Modifier.testTag("queue-claimed"))
                else if (job.claimedOther) Text("by ${job.claimedByName ?: "someone"}", Modifier.testTag("queue-claimed"), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(job.title, style = MaterialTheme.typography.headlineSmall)
            job.subtitle?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
            job.customer?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            StatusPill(job.status, Modifier.testTag("queue-status"))
            QUEUE_RECOMMENDED_ACTION[job.status]?.let { Text(it, Modifier.testTag("queue-recommended"), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary) }
            job.due?.takeIf { it.isNotBlank() }?.let { Text("Due $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            job.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 6) }
            lane.workLogs?.takeIf { it.jobId == job.id }?.let { WorkLogHistory(it) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                OutlinedButton(onClick = onNote, enabled = !lane.busy, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-note")) { Text("Note") }
                if (lane.workLogs != null) OutlinedButton(onClick = onLogWork, enabled = !lane.busy, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-log-work")) { Text("Log work") }
                OutlinedButton(onClick = actions.toggleClaim, enabled = !lane.busy, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-claim")) {
                    Text(if (job.claimedMine) "Release" else "Claim")
                }
            }
            if (lane.showSms && job.status in QUEUE_SMS_REMIND_STATUSES) {
                OutlinedButton(onClick = actions.sendSms, enabled = !lane.busy, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("queue-sms")) {
                    Text(if (job.status == "awaiting_go_ahead") "Remind customer (SMS)" else "Notify ready (SMS)")
                }
            }
            Text(
                "Swipe right: " + (rightTarget?.let { statusLabel(it) } ?: "final step") + "  ·  Swipe left: " + (leftTarget?.let { "back to ${statusLabel(it)}" } ?: "skip"),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable private fun WorkLogHistory(w: QueueWorkLogs) {
    if (w.loading) { Text("Loading work log...", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant); return }
    if (w.logs.isEmpty()) return
    Column(Modifier.fillMaxWidth().testTag("queue-worklogs"), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("Work log", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        w.logs.asReversed().take(5).forEach { log ->
            val note = runCatching { log.note }.getOrNull().orEmpty()
            val date = runCatching { log.createdAt.take(10) }.getOrDefault("")
            Text(listOf(note.ifBlank { "(no note)" }, if (log.minutes > 0) "${log.minutes}m" else "", date).filter { it.isNotBlank() }.joinToString(" · "),
                style = MaterialTheme.typography.bodySmall)
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
    onNoUpdate: () -> Unit,
    onMoveWithNote: () -> Unit,
) {
    Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onBackOrSkip, enabled = !busy && canGoBack, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-back")) { Text("Back") }
            OutlinedButton(onClick = onSkip, enabled = !busy, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-skip")) { Text("Skip") }
            OutlinedButton(onClick = onUndo, enabled = canUndo, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-undo")) { Text("Undo") }
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onNoUpdate, enabled = !busy, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-no-update")) { Text("No update") }
            OutlinedButton(onClick = onMoveWithNote, enabled = canAdvance, modifier = Modifier.weight(1f).heightIn(min = 48.dp).testTag("queue-move-note")) { Text("Move + note") }
        }
        val next = job.rightTarget
        Button(onClick = onAdvance, enabled = canAdvance, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("queue-advance")) {
            Text(if (busy) "Saving..." else next?.let { "Move to ${statusLabel(it)}" } ?: "Final step")
        }
    }
}

/**
 * Note panel with quick-pick chips (web NOTE / NO UPDATE / ADVANCE panels). [required] blocks an empty note; otherwise
 * an empty note is passed as null. [onConfirm] gets the chosen chip or typed text.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable private fun NoteDialog(title: String, subtitle: String, chips: List<String>, confirmLabel: String, required: Boolean, onDismiss: () -> Unit, onConfirm: (String?) -> Unit) {
    var chip by rememberSaveable { mutableStateOf("") }
    var text by rememberSaveable { mutableStateOf("") }
    val note = chip.ifBlank { text.trim() }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (chips.isNotEmpty()) FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    chips.forEachIndexed { i, c ->
                        FilterChip(chip == c, { chip = if (chip == c) "" else c; text = "" }, { Text(c) }, Modifier.heightIn(min = 48.dp).testTag("queue-chip-$i"))
                    }
                }
                OutlinedTextField(text, { text = it; chip = "" }, Modifier.fillMaxWidth().testTag("queue-dialog-text"), label = { Text(if (required) "Type a note" else "Or type a custom note") })
            }
        },
        confirmButton = {
            TextButton({ onConfirm(note.ifBlank { null }) }, Modifier.heightIn(min = 48.dp).testTag("queue-dialog-confirm"), enabled = !required || note.isNotBlank()) { Text(confirmLabel) }
        },
        dismissButton = { TextButton(onDismiss, Modifier.heightIn(min = 48.dp).testTag("queue-dialog-cancel")) { Text("Cancel") } },
    )
}

@Composable private fun LogWorkDialog(onDismiss: () -> Unit, onConfirm: (String, Int?) -> Unit) {
    var note by rememberSaveable { mutableStateOf("") }
    var minutes by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Log work") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Status unchanged", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(note, { note = it }, Modifier.fillMaxWidth().testTag("queue-dialog-text"), label = { Text("What was done") }, minLines = 3)
                OutlinedTextField(minutes, { minutes = it.filter(Char::isDigit).take(4) }, Modifier.fillMaxWidth().testTag("queue-dialog-minutes"),
                    label = { Text("Time spent (minutes, optional)") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true)
            }
        },
        confirmButton = {
            TextButton({ onConfirm(note.trim(), minutes.toIntOrNull()) }, Modifier.heightIn(min = 48.dp).testTag("queue-dialog-confirm"), enabled = note.isNotBlank()) { Text("Save log") }
        },
        dismissButton = { TextButton(onDismiss, Modifier.heightIn(min = 48.dp).testTag("queue-dialog-cancel")) { Text("Cancel") } },
    )
}
