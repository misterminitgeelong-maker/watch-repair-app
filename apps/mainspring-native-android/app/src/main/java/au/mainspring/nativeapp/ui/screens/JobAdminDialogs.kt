package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.api.CustomerAccountRead

/** Confirmation before a job (and its quotes, invoices, photos and history) is permanently deleted. */
@Composable
fun DeleteJobDialog(jobLabel: String, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Delete job?") },
        text = { Text("This permanently deletes $jobLabel with its quotes, invoices, photos and history. This cannot be undone.") },
        confirmButton = { TextButton(onClick = onConfirm, modifier = Modifier.testTag("delete-job-confirm")) { Text("Delete", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

/** Confirmation before a job is duplicated. */
@Composable
fun DuplicateJobDialog(onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Duplicate job?") },
        text = { Text("Creates a new job for the same customer with a fresh status.") },
        confirmButton = { TextButton(onClick = onConfirm) { Text("Duplicate") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

/**
 * Picker for the B2B customer account on a job. Like web, only accounts that include the job's customer are
 * offered when [customerId] is known. "Unassign" clears the account.
 */
@Composable
fun AccountPickerDialog(
    accounts: List<CustomerAccountRead>,
    loading: Boolean,
    customerId: String?,
    currentAccountId: String?,
    onPick: (String?) -> Unit,
    onDismiss: () -> Unit,
) {
    val options = if (customerId.isNullOrBlank()) accounts else accounts.filter { customerId in it.customerIds }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Business account") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (!loading && options.isEmpty()) Text("No business accounts include this customer.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                options.forEach { a ->
                    val current = a.id == currentAccountId
                    TextButton(onClick = { onPick(a.id) }, enabled = !current, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                        Text(a.name + (a.code?.takeIf { it.isNotBlank() }?.let { " ($it)" } ?: "") + if (current) " (assigned)" else "", Modifier.fillMaxWidth())
                    }
                }
                if (currentAccountId != null) TextButton(onClick = { onPick(null) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("account-unassign")) { Text("Unassign", Modifier.fillMaxWidth()) }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
    )
}
