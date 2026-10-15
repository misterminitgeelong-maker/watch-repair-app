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
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.previewQueueSwipe
import au.mainspring.nativeapp.ui.*
import kotlinx.coroutines.launch

/**
 * Repair queue swipe triage (web RepairQueueModal, watch lane). Swipe the top card right to move the job
 * forward one status, left to step it back (or skip it when there is no earlier step). Buttons do the same,
 * and Undo reverses the last action. Status-only; the customer is never messaged from here.
 */
@Composable
fun RepairQueueScreen(
    onBack: () -> Unit,
    onOpenJob: (String) -> Unit,
    viewModel: RepairQueueViewModel = viewModel(),
) {
    val s by viewModel.state.collectAsStateWithLifecycle()
    val online by ConnectivityMonitor.online.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        BackLargeHeader("More", "Workshop", "Repair queue", onBack)
        if (!online) {
            Text("Offline. Moves are paused until you reconnect.", Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).testTag("queue-offline"),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
        when {
            s.loading -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator(Modifier.testTag("queue-loading")) }
            s.error != null && s.total == 0 && s.queue.isEmpty() -> Column(Modifier.fillMaxWidth().padding(16.dp).testTag("queue-load-error"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(s.error.orEmpty(), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                OutlinedButton(onClick = viewModel::refresh, modifier = Modifier.testTag("queue-retry")) { Text("Retry") }
            }
            s.total == 0 -> EmptyState("No jobs to triage", "Watch repairs waiting on a step appear here.", "Refresh", viewModel::refresh, Modifier.testTag("queue-empty"))
            else -> {
                Progress(s.advanced, s.total, s.skipped)
                s.error?.let {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp).testTag("queue-error"), verticalAlignment = Alignment.CenterVertically) {
                        Text(it, Modifier.weight(1f), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = viewModel::dismissError) { Text("Dismiss") }
                    }
                }
                val current = s.current
                if (current == null) {
                    Column(Modifier.weight(1f).fillMaxWidth().testTag("queue-clear"), horizontalAlignment = Alignment.CenterHorizontally) {
                        EmptyState("Queue clear", "You moved ${s.advanced} job${if (s.advanced == 1) "" else "s"} along.", "Refresh", viewModel::refresh)
                        TextButton(onClick = viewModel::undo, enabled = s.canUndo, modifier = Modifier.testTag("queue-undo")) { Text("Undo last") }
                    }
                } else {
                    Box(Modifier.weight(1f).fillMaxWidth().padding(16.dp)) {
                        s.queue.getOrNull(2)?.let { BackdropCard(it, 2) }
                        s.queue.getOrNull(1)?.let { BackdropCard(it, 1) }
                        SwipeCard(current, s.canAdvance, s.canGoBack, s.canUndo,
                            onSwipeRight = viewModel::advance, onSwipeLeft = viewModel::backOrSkip,
                            onSkip = viewModel::skip, onUndo = viewModel::undo, onOpen = { onOpenJob(current.id) })
                    }
                    Controls(
                        current, s.busy, s.canAdvance, s.canGoBack, s.canUndo,
                        onAdvance = viewModel::advance, onBackOrSkip = viewModel::backOrSkip, onSkip = viewModel::skip, onUndo = viewModel::undo,
                    )
                }
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

@Composable private fun BackdropCard(job: RepairJobRead, depth: Int) {
    val calibre = LocalCalibre.current
    Surface(
        Modifier.fillMaxWidth().fillMaxHeight(0.9f).padding(top = (depth * 10).dp, start = (depth * 6).dp, end = (depth * 6).dp),
        shape = if (calibre) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceVariant,
        border = if (calibre) BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant) else null,
    ) {}
}

@Composable private fun SwipeCard(
    job: RepairJobRead,
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
    val leftTarget = previewQueueSwipe(job.status, "left")
    val rightTarget = previewQueueSwipe(job.status, "right")
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
            val watch = listOfNotNull(job.watchBrand, job.watchModel).joinToString(" ")
            if (watch.isNotBlank()) Text(watch, style = MaterialTheme.typography.bodyLarge)
            job.customerName?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            StatusPill(job.status, Modifier.testTag("queue-status"))
            job.collectionDate?.takeIf { it.isNotBlank() }?.let { Text("Due $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
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
    job: RepairJobRead,
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
            OutlinedButton(onClick = onBackOrSkip, enabled = !busy && canGoBack, modifier = Modifier.weight(1f).testTag("queue-back")) { Text("Back") }
            OutlinedButton(onClick = onSkip, enabled = !busy, modifier = Modifier.weight(1f).testTag("queue-skip")) { Text("Skip") }
            OutlinedButton(onClick = onUndo, enabled = canUndo, modifier = Modifier.weight(1f).testTag("queue-undo")) { Text("Undo") }
        }
        val next = previewQueueSwipe(job.status, "right")
        Button(onClick = onAdvance, enabled = canAdvance, modifier = Modifier.fillMaxWidth().testTag("queue-advance")) {
            Text(if (busy) "Saving..." else next?.let { "Move to ${statusLabel(it)}" } ?: "Final step")
        }
    }
}
