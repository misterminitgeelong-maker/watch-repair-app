package au.mainspring.nativeapp.ui.screens

import android.content.Intent
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay

/** Moving a ticket here needs a reason, so the popup asks for one first (it is saved as the status note). */
internal val REASON_STATUSES = setOf("no_go", "failed_job")

/** What the "Moved to X. Undo" message needs: the ticket, where it came from and went, and whether the move is waiting to sync. */
data class BoardMoveToast(val id: String, val from: String, val to: String, val toLabel: String, val queued: Boolean, val extra: String? = null,
    val nonce: Long = System.nanoTime())

/**
 * One kanban ticket that opens on a normal tap and, on press-and-hold (about half a second, cancelled if the finger scrolls),
 * pops a small menu beside it: Open job, Move to (opens the stage list) and Call customer.
 * [targets] are (status, label) pairs; [onMove] gets the chosen status and the reason when [REASON_STATUSES] asked for one.
 */
@OptIn(ExperimentalFoundationApi::class)
@Composable internal fun HoldMenuTicket(label: String, status: String, targets: List<Pair<String, String>>, canMove: Boolean, phone: String?,
    onOpen: () -> Unit, onMove: (status: String, reason: String?) -> Unit, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    var menu by remember { mutableIntStateOf(0) }  // 0 closed, 1 main, 2 stage list
    var reasonFor by remember { mutableStateOf<Pair<String, String>?>(null) }
    val haptic = LocalHapticFeedback.current
    val context = LocalContext.current
    val canMoveNow = canMove && targets.isNotEmpty()
    Box(modifier.combinedClickable(onClick = onOpen, onLongClick = { haptic.performHapticFeedback(HapticFeedbackType.LongPress); menu = 1 },
        onLongClickLabel = "Show ticket menu", role = Role.Button)
        .semantics { if(canMoveNow) customActions = listOf(CustomAccessibilityAction("Move to…") { menu = 2; true }) }) {
        content()
        DropdownMenu(expanded = menu == 1, onDismissRequest = { menu = 0 }, modifier = Modifier.testTag("hold-menu")) {
            DropdownMenuItem(text = { Text("Open job") }, onClick = { menu = 0; onOpen() }, modifier = Modifier.testTag("hold-open"))
            if(canMoveNow) DropdownMenuItem(text = { Row(Modifier.fillMaxWidth()) { Text("Move to", Modifier.weight(1f)); Text("›") } }, onClick = { menu = 2 }, modifier = Modifier.testTag("hold-move"))
            if(!phone.isNullOrBlank()) DropdownMenuItem(text = { Text("Call customer") }, modifier = Modifier.testTag("hold-call"), onClick = {
                menu = 0
                val digits = phone.filter { it.isDigit() || it == '+' }
                if(digits.isNotEmpty()) launchContact(context, Intent(Intent.ACTION_DIAL, android.net.Uri.parse("tel:$digits")))
            })
        }
        DropdownMenu(expanded = menu == 2, onDismissRequest = { menu = 0 }, modifier = Modifier.testTag("hold-stages")) {
            DropdownMenuItem(text = { Text("‹ Back") }, onClick = { menu = 1 })
            targets.forEach { (target, targetLabel) ->
                val current = target == status
                DropdownMenuItem(text = { Text(if(current) "$targetLabel (now)" else targetLabel) }, enabled = !current, modifier = Modifier.testTag("hold-target-$target"), onClick = {
                    menu = 0
                    if(target in REASON_STATUSES) reasonFor = target to targetLabel else onMove(target, null)
                })
            }
        }
    }
    reasonFor?.let { (target, targetLabel) ->
        var reason by remember(target) { mutableStateOf("") }
        AlertDialog(onDismissRequest = { reasonFor = null }, title = { Text("Reason for $targetLabel") },
            text = { OutlinedTextField(reason, { reason = it.take(500) }, Modifier.fillMaxWidth().testTag("move-reason"), label = { Text("Reason") }, minLines = 2) },
            confirmButton = { TextButton({ reasonFor = null; onMove(target, reason.trim()) }, enabled = reason.isNotBlank(), modifier = Modifier.testTag("move-reason-confirm")) { Text("Move to $targetLabel") } },
            dismissButton = { TextButton({ reasonFor = null }) { Text("Cancel") } })
    }
}

/** "Moved to X. Undo" (or "Saved offline, will sync") message that clears itself after a few seconds. */
@Composable internal fun BoardMoveToastBar(toast: BoardMoveToast?, onUndo: (BoardMoveToast) -> Unit, onDismiss: () -> Unit, modifier: Modifier = Modifier) {
    LaunchedEffect(toast?.nonce) { if(toast != null) { delay(7000); onDismiss() } }
    if(toast == null) return
    Surface(modifier.padding(horizontal = 16.dp).testTag("move-toast"), shape = RoundedCornerShape(8.dp), color = MaterialTheme.colorScheme.inverseSurface, shadowElevation = 6.dp) {
        Row(Modifier.heightIn(min = 48.dp).padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(buildString { append("Moved to ${toast.toLabel}"); if(toast.queued) append(" (saved offline, will sync)"); toast.extra?.let { append(". $it") } },
                Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.inverseOnSurface)
            TextButton({ onUndo(toast) }, Modifier.testTag("move-undo")) { Text("Undo", color = MaterialTheme.colorScheme.inversePrimary) }
        }
    }
}
