package au.mainspring.nativeapp.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.SavedJobView
import au.mainspring.nativeapp.WorkflowStep
import au.mainspring.nativeapp.daysInShopSeverity
import au.mainspring.nativeapp.daysInShopText
import au.mainspring.nativeapp.workflowStepIndex

/** "N days in shop" with web colour bands (7+ warn, 14+ alert). */
@Composable
fun DaysInShopLabel(days: Int, modifier: Modifier = Modifier) {
    val color = when (daysInShopSeverity(days)) {
        2 -> MaterialTheme.colorScheme.error
        1 -> Color(0xFF9A5010)
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Text(daysInShopText(days), modifier.testTag("days-in-shop"), style = MaterialTheme.typography.labelMedium, color = color)
}

/**
 * Workflow rail: where the job sits across the web's steps plus one-tap suggestions for the
 * next sensible statuses. [onMove] is only offered when [enabled].
 */
@Composable
fun WorkflowRail(
    steps: List<WorkflowStep>,
    status: String,
    suggestions: List<String>,
    labelFor: (String) -> String,
    enabled: Boolean,
    onMove: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val current = workflowStepIndex(steps, status)
    val calibre = LocalCalibre.current
    Column(modifier.fillMaxWidth().testTag("workflow-rail"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (calibre) MonoLabel("Workflow") else Text("Workflow", Modifier.semantics { heading() }, style = MaterialTheme.typography.titleSmall)
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            steps.forEachIndexed { i, step ->
                val state = if (i < current) "done" else if (i == current) "current" else "upcoming"
                TabChip(selected = i == current, onClick = {}, enabled = false,
                    label = { Text((if (i < current) "✓ " else "") + step.label) },
                    modifier = Modifier.semantics { contentDescription = "${step.label}, $state" })
            }
        }
        if (suggestions.isNotEmpty()) {
            Text("Next", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                suggestions.forEachIndexed { i, s ->
                    val action: @Composable () -> Unit = { Text(labelFor(s)) }
                    if (i == 0) PrimaryAction(onClick = { onMove(s) }, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp).testTag("rail-next-$s")) { action() }
                    else SecondaryAction(onClick = { onMove(s) }, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp).testTag("rail-next-$s")) { action() }
                }
            }
        }
    }
}

/** Previous / next job within the list the user came from. */
@Composable
fun JobNavBar(position: Pair<Int, Int>?, prevId: String?, nextId: String?, onGo: (String) -> Unit, enabled: Boolean = true, modifier: Modifier = Modifier) {
    if (prevId == null && nextId == null) return
    Row(modifier.fillMaxWidth().testTag("job-nav"), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        TextButton(onClick = { prevId?.let(onGo) }, enabled = enabled && prevId != null, modifier = Modifier.heightIn(min = 48.dp).testTag("job-prev")) { Text("‹ Previous") }
        position?.let { (i, n) -> Text("$i of $n", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        TextButton(onClick = { nextId?.let(onGo) }, enabled = enabled && nextId != null, modifier = Modifier.heightIn(min = 48.dp).testTag("job-next")) { Text("Next ›") }
    }
}

/** Row of saved-view chips plus "Save view" and "Manage" actions. [current] is what gets saved. */
@Composable
fun SavedViewsRow(
    views: List<SavedJobView>,
    current: () -> SavedJobView,
    onApply: (SavedJobView) -> Unit,
    onSave: (SavedJobView) -> Unit,
    onDelete: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var naming by remember { mutableStateOf(false) }
    var managing by remember { mutableStateOf(false) }
    var draft by remember { mutableStateOf("") }
    Row(modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        views.forEach { v -> TabChip(selected = false, onClick = { onApply(v) }, label = { Text(v.name) }, modifier = Modifier.testTag("saved-view-${v.name}")) }
        TabChip(selected = false, onClick = { draft = ""; naming = true }, label = { Text("+ Save view") }, modifier = Modifier.testTag("saved-view-save"))
        if (views.isNotEmpty()) TabChip(selected = false, onClick = { managing = true }, label = { Text("Manage views") }, modifier = Modifier.testTag("saved-view-manage"))
    }
    if (naming) AlertDialog(
        onDismissRequest = { naming = false },
        title = { Text("Save current view") },
        text = {
            AtelierTextField(value = draft, onValueChange = { draft = it.take(au.mainspring.nativeapp.SavedViewsStore.MAX_NAME) },
                label = { Text("View name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        },
        confirmButton = { TextButton(onClick = { onSave(current().copy(name = draft.trim())); naming = false }, enabled = draft.isNotBlank(), modifier = Modifier.heightIn(min = 48.dp)) { Text("Save") } },
        dismissButton = { TextButton(onClick = { naming = false }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Cancel") } },
    )
    if (managing) AlertDialog(
        onDismissRequest = { managing = false },
        title = { Text("Saved views") },
        text = {
            Column {
                if (views.isEmpty()) Text("No saved views.")
                views.forEach { v ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(v.name, Modifier.weight(1f))
                        TextButton(onClick = { onDelete(v.name) }, modifier = Modifier.heightIn(min = 48.dp).semantics { contentDescription = "Delete saved view ${v.name}" }) { Text("Delete") }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = { managing = false }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Close") } },
    )
}


/** One-tap Call / Text / Email for the customer, right under the job header where a thumb can reach it. */
@Composable fun ContactQuickActions(phone: String?, email: String?, modifier: Modifier = Modifier) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val p = phone?.takeIf { it.isNotBlank() }
    val e = email?.takeIf { it.isNotBlank() }
    if(p == null && e == null) return
    var error by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf<String?>(null) }
    val digits = p?.filter { it.isDigit() || it == '+' }
    androidx.compose.foundation.layout.Column(modifier.testTag("contact-quick-actions"), verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(4.dp)) {
        androidx.compose.foundation.layout.Row(Modifier.fillMaxWidth(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
            if(p != null) {
                SecondaryAction(onClick = { error = au.mainspring.nativeapp.ui.screens.launchContact(ctx, android.content.Intent(android.content.Intent.ACTION_DIAL, android.net.Uri.parse("tel:$digits"))) },
                    modifier = Modifier.weight(1f).heightIn(min = 48.dp)) { Text("Call") }
                SecondaryAction(onClick = { error = au.mainspring.nativeapp.ui.screens.launchContact(ctx, android.content.Intent(android.content.Intent.ACTION_SENDTO, android.net.Uri.parse("smsto:$digits"))) },
                    modifier = Modifier.weight(1f).heightIn(min = 48.dp)) { Text("Text") }
            }
            if(e != null) SecondaryAction(onClick = { error = au.mainspring.nativeapp.ui.screens.launchContact(ctx, android.content.Intent(android.content.Intent.ACTION_SENDTO, android.net.Uri.parse("mailto:" + android.net.Uri.encode(e)))) },
                modifier = Modifier.weight(1f).heightIn(min = 48.dp)) { Text("Email") }
        }
        error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
    }
}
