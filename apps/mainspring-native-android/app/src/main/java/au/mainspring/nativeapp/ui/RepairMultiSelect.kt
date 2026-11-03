package au.mainspring.nativeapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.InputChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

/** One selectable repair. [priceCents] is null for quote-required items; [priceLabel] is the text shown beside the name. */
data class RepairOption(val key: String, val name: String, val priceCents: Int?, val priceLabel: String, val group: String? = null)

const val REPAIR_PLACEHOLDER = "Select repairs (optional)"

/** "Select repairs (optional)" when empty, else "3 repairs · $120.00" (+ " + quote" when any selected item needs a quote). */
fun repairSummary(count: Int, totalCents: Int?, hasQuote: Boolean = false, currency: String = "AUD"): String {
    if(count <= 0) return REPAIR_PLACEHOLDER
    val noun = if(count == 1) "1 repair" else "$count repairs"
    val price = totalCents?.takeIf { it > 0 || !hasQuote }?.let { formatCents(it, currency) }
    return when {
        price == null -> "$noun · quote required"
        hasQuote -> "$noun · $price + quote"
        else -> "$noun · $price"
    }
}

/** Case-insensitive match on name or group; blank query matches everything. */
fun filterRepairs(options: List<RepairOption>, query: String): List<RepairOption> {
    val q = query.trim()
    return if(q.isEmpty()) options else options.filter { it.name.contains(q, true) || it.group.orEmpty().contains(q, true) }
}

/**
 * Compact dropdown row for choosing repairs. Tapping opens a searchable multi-select sheet; selected repairs
 * show as removable chips below. Selection state lives with the caller ([onToggle] flips one key).
 */
@OptIn(ExperimentalMaterial3Api::class, androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable fun RepairMultiSelect(
    options: List<RepairOption>, selectedKeys: Set<String>, onToggle: (String) -> Unit,
    totalCents: Int?, modifier: Modifier = Modifier, enabled: Boolean = true, currency: String = "AUD",
) {
    var open by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable { mutableStateOf("") }
    val selected = options.filter { it.key in selectedKeys }
    val hasQuote = selected.any { it.priceCents == null }
    val summary = repairSummary(selected.size, totalCents, hasQuote, currency)
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Surface(
            onClick = { open = true }, enabled = enabled, shape = RoundedCornerShape(6.dp),
            color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp).testTag("repair-select-field")
                .semantics { contentDescription = "Repairs. $summary" },
        ) {
            Row(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(summary, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge,
                    color = if(selected.isEmpty()) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface)
                Text("▾", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        if(selected.isNotEmpty()) {
            androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                selected.forEach { item ->
                    InputChip(
                        selected = true, onClick = { onToggle(item.key) }, enabled = enabled,
                        label = { Text(item.name) },
                        trailingIcon = { Text("✕", Modifier.semantics { contentDescription = "Remove ${item.name}" }) },
                        modifier = Modifier.testTag("repair-chip-${item.key}"),
                    )
                }
            }
            Text("Total: " + (totalCents?.let { formatCents(it, currency) } ?: "Quote required") + if(hasQuote && totalCents != null) " + quote" else "",
                style = MaterialTheme.typography.titleSmall, modifier = Modifier.testTag("repair-total"))
        }
    }
    if(open) {
        ModalBottomSheet(onDismissRequest = { open = false }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
            Column(Modifier.fillMaxWidth().imePadding().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = query, onValueChange = { query = it }, singleLine = true,
                    placeholder = { Text("Search repairs...", color = MaterialTheme.colorScheme.onSurfaceVariant) },
                    modifier = Modifier.fillMaxWidth().testTag("repair-search").semantics { contentDescription = "Search repairs" },
                )
                val shown = filterRepairs(options, query)
                if(shown.isEmpty()) Text("No repairs match your search.", color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 8.dp))
                LazyColumn(Modifier.weight(1f, fill = false).heightIn(max = 420.dp)) {
                    items(shown, key = { it.key }) { item ->
                        val checked = item.key in selectedKeys
                        Row(
                            Modifier.fillMaxWidth().heightIn(min = 56.dp).testTag("repair-option-${item.key}")
                                .clickable(enabled = enabled, role = Role.Checkbox) { onToggle(item.key) },
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Checkbox(checked = checked, onCheckedChange = null, enabled = enabled)
                            Text(item.name, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                            Text(item.priceLabel, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                PrimaryAction(onClick = { open = false; query = "" }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("repair-done")) { Text("Done") }
                androidx.compose.foundation.layout.Spacer(Modifier.padding(bottom = 8.dp))
            }
        }
    }
}
