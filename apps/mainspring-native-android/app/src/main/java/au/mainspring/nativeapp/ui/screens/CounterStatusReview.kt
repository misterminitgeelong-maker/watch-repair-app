package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import androidx.compose.material3.*
import androidx.compose.runtime.*

@Composable
fun CounterStatusReview(unknown: Boolean, request: String, reviewed: Boolean, loading: Boolean, onRefresh: () -> Unit, onReviewed: () -> Unit) {
    var confirm by remember { mutableStateOf(false) }
    if(unknown) {
        Text("The previous status update has no confirmed result. Check the refreshed job and history before continuing.")
        if(request.isNotBlank()) Text(request)
        OutlinedButton(onRefresh, enabled = !loading) { Text("Refresh status and history") }
        OutlinedButton({ confirm = true }, enabled = reviewed && !loading) { Text("Reviewed status and history") }
    }
    if(confirm) AlertDialog(onDismissRequest = { confirm = false }, title = { Text("Confirm status review") },
        text = { Text("I checked the current job and status history. Clear the interrupted request so I can make a new status change if needed? Status changes may notify the customer.") },
        confirmButton = { TextButton({ confirm = false; onReviewed() }) { Text("Confirm review") } }, dismissButton = { TextButton({ confirm = false }) { Text("Cancel") } })
}
