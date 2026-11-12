package au.mainspring.nativeapp.ui

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

/*
 * Shared building blocks from the "seamless native pass" designs (Figma page "Seamless native pass (12 Nov)"):
 * a compact dropdown filter, a bottom-sheet picker with big selectable rows, loading placeholder rows and a calm empty state.
 */

/** Compact outlined dropdown for list filters. [options] maps a stored key (null = all) to its label; the button shows the selected label. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun FilterDropdown(label: String, options: List<Pair<String?, String>>, selected: String?, onSelect: (String?) -> Unit, modifier: Modifier = Modifier) {
    var open by remember { mutableStateOf(false) }
    val current = options.firstOrNull { it.first == selected }?.second ?: label
    Box(modifier) {
        Surface({ open = true }, Modifier.heightIn(min = 40.dp).semantics { role = Role.DropdownList; contentDescription = "$label: $current" },
            shape = RoundedCornerShape(8.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)) {
            Row(Modifier.padding(start = 12.dp, end = 10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(current, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text("▾", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        DropdownMenu(open, { open = false }) {
            options.forEach { (key, text) ->
                DropdownMenuItem(
                    text = { Text(text, fontWeight = if(key == selected) FontWeight.Bold else FontWeight.Normal) },
                    onClick = { open = false; onSelect(key) },
                    trailingIcon = if(key == selected) ({ Text("✓", color = MaterialTheme.colorScheme.primary) }) else null)
            }
        }
    }
}

/** Bottom sheet that asks the person to pick one option from big selectable rows. Replaces dialogs of text links. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun <T> PickerSheet(title: String, options: List<Pair<T, String>>, selected: T?, onSelect: (T) -> Unit, onDismiss: () -> Unit, subtitle: String? = null) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = MaterialTheme.colorScheme.surface) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            subtitle?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            Spacer(Modifier.height(8.dp))
            options.forEach { (value, text) ->
                val on = value == selected
                Surface({ onSelect(value) }, Modifier.fillMaxWidth().heightIn(min = 48.dp).semantics { this.selected = on; role = Role.RadioButton },
                    shape = RoundedCornerShape(10.dp), color = if(on) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
                    border = if(on) BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null) {
                    Row(Modifier.padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        RadioButton(on, onClick = null)
                        Text(text, style = MaterialTheme.typography.bodyLarge, fontWeight = if(on) FontWeight.Bold else FontWeight.Normal)
                    }
                }
            }
        }
    }
}

/** Grey placeholder rows shaped like list rows, with a soft pulse. Use instead of a spinner on a blank screen. */
@Composable fun SkeletonRows(modifier: Modifier = Modifier, count: Int = 6) {
    val pulse = rememberInfiniteTransition(label = "skeleton")
    val alpha by pulse.animateFloat(0.45f, 1f, infiniteRepeatable(tween(900, easing = LinearEasing), RepeatMode.Reverse), label = "skeleton-alpha")
    val bar = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = alpha)
    Column(modifier.fillMaxWidth().padding(12.dp).semantics { contentDescription = "Loading" }, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        repeat(count) { i ->
            Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(MaterialTheme.colorScheme.surface)
                .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(10.dp)).padding(12.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(Modifier.size(44.dp).clip(CircleShape).background(bar))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Box(Modifier.width(150.dp).height(12.dp).clip(RoundedCornerShape(4.dp)).background(bar))
                    Box(Modifier.width((100 + (i % 3) * 30).dp).height(10.dp).clip(RoundedCornerShape(4.dp)).background(bar))
                }
                Box(Modifier.width(56.dp).height(20.dp).clip(RoundedCornerShape(10.dp)).background(bar))
            }
        }
    }
}

/** A calm "nothing here" state with one next action. Empty is not an error: no red. */
@Composable fun CalmEmptyState(title: String, body: String, modifier: Modifier = Modifier, actionLabel: String? = null, onAction: (() -> Unit)? = null) {
    Column(modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(Modifier.size(72.dp).clip(CircleShape).background(MaterialTheme.colorScheme.primaryContainer), contentAlignment = Alignment.Center) {
            ToolIcon("search", size = 32.dp, color = MaterialTheme.colorScheme.primary)
        }
        Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
        Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        if(actionLabel != null && onAction != null) OutlinedButton(onAction, Modifier.heightIn(min = 44.dp)) { Text(actionLabel) }
    }
}
