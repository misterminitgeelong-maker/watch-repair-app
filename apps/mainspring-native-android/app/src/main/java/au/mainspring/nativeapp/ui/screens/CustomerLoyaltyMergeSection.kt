package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.CustomerDetailUiState
import au.mainspring.nativeapp.CustomerDetailViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.CustomerRead
import au.mainspring.nativeapp.ui.*

/** Loyalty panel (read for everyone, adjust for manager and above) and the owner/manager duplicate-merge flow. */
@Composable
fun LoyaltyAndMergeSection(state: CustomerDetailUiState, vm: CustomerDetailViewModel, customerName: String) {
    val canManage = TokenStore.canManageInvoices()
    var adjusting by remember { mutableStateOf(false) }
    var merging by remember { mutableStateOf(false) }
    var mergeTarget by remember { mutableStateOf<CustomerRead?>(null) }
    state.loyalty?.let { profile ->
        val loyalty = profile.loyalty
        SectionLabel("Loyalty")
        FlatPanel(Modifier.testTag("customer-loyalty-panel")) {
            DetailRow("Tier", loyalty.tierLabel ?: loyalty.tierName.orEmpty())
            DetailRow("Points", loyalty.pointsBalance.toString() + (loyalty.pointsDollarValue?.let { " (worth ${String.format(java.util.Locale.US, "%.2f", it)})" } ?: ""))
            DetailRow("Spend, last 12 months", formatCents(loyalty.rolling12mSpendCents.coerceAtMost(Int.MAX_VALUE.toLong()).toInt(), TokenStore.shopValue("currency") ?: "AUD"))
            profile.recentLedger.take(5).forEach { entry ->
                DetailRow((if(entry.pointsDelta > 0) "+" else "") + entry.pointsDelta,
                    listOfNotNull(entry.note?.takeIf { it.isNotBlank() }, entry.entryType?.let { statusLabel(it) }).firstOrNull().orEmpty())
            }
            if(canManage) SecondaryAction({ adjusting = true }, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("customer-loyalty-adjust")) { Text("Adjust points") }
        }
    }
    if(canManage) {
        SectionLabel("Duplicates")
        SecondaryAction({ merging = true }, Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("customer-merge")) { Text("Merge a duplicate customer") }
    }
    if(adjusting) {
        var delta by remember { mutableStateOf("") }
        var note by remember { mutableStateOf("") }
        val points = delta.trim().toIntOrNull()?.takeIf { it != 0 }
        AlertDialog(onDismissRequest = { adjusting = false }, title = { Text("Adjust points") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                AtelierTextField(delta, { delta = it }, singleLine = true, label = { Text("Points (negative to remove)") }, modifier = Modifier.fillMaxWidth(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                AtelierTextField(note, { note = it }, label = { Text("Reason") }, modifier = Modifier.fillMaxWidth())
                state.loyaltyError?.let { ErrorBanner(it) }
            } },
            confirmButton = { PrimaryAction({ vm.adjustLoyalty(points ?: 0, note) { adjusting = false } }, enabled = points != null && note.isNotBlank() && !state.loyaltySaving) { Text("Apply") } },
            dismissButton = { SecondaryAction({ adjusting = false }) { Text("Cancel") } })
    }
    if(merging) {
        var query by remember { mutableStateOf("") }
        AlertDialog(onDismissRequest = { merging = false; vm.clearMerge() }, title = { Text("Merge duplicate") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Find the duplicate record. Its watches and jobs move onto $customerName and the duplicate is deleted.", style = MaterialTheme.typography.bodyMedium)
                AtelierTextField(query, { query = it; vm.searchMergeCandidates(it) }, singleLine = true, label = { Text("Search customers") }, modifier = Modifier.fillMaxWidth())
                if(state.mergeSearching) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.mergeError?.let { ErrorBanner(it) }
                state.mergeResults.take(6).forEach { c ->
                    TextButton({ mergeTarget = c }, Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                        Text(listOfNotNull(c.fullName, c.phone?.takeIf { it.isNotBlank() }, c.email?.takeIf { it.isNotBlank() }).joinToString(" · "),
                            Modifier.fillMaxWidth(), textAlign = TextAlign.Start)
                    }
                }
            } },
            confirmButton = { TextButton({ merging = false; vm.clearMerge() }) { Text("Close") } })
    }
    mergeTarget?.let { target ->
        AlertDialog(onDismissRequest = { if(!state.merging) mergeTarget = null }, title = { Text("Merge ${target.fullName} into $customerName?") },
            text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("${target.fullName} will be permanently deleted. Their watches, shoe jobs and mobile jobs will move to $customerName. This cannot be undone.")
                state.mergeError?.let { ErrorBanner(it) }
            } },
            confirmButton = { PrimaryAction({ vm.mergeDuplicate(target.id) }, Modifier.testTag("customer-merge-confirm"), enabled = !state.merging) { Text("Merge and delete duplicate") } },
            dismissButton = { SecondaryAction({ mergeTarget = null }, enabled = !state.merging) { Text("Cancel") } })
    }
    LaunchedEffect(state.merged) { if(state.merged) { merging = false; mergeTarget = null; vm.mergeNoticeShown() } }
}
