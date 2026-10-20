package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.parseCustomServicePrice

/** Inline "Add custom service" form used by the watch and shoe intake pickers (web WatchServicePicker / ShoeServicePicker). */
@Composable
fun AddCustomServiceDialog(busy: Boolean, error: String?, onAdd: (name: String, priceCents: Int) -> Unit, onDismiss: () -> Unit) {
    var name by remember { mutableStateOf("") }
    var price by remember { mutableStateOf("") }
    val cents = parseCustomServicePrice(price)
    AlertDialog(onDismissRequest = { if(!busy) onDismiss() }, title = { Text("Add custom service") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                AtelierTextField(name, { name = it }, label = { Text("Service name") }, placeholder = { Text("e.g. Custom engraving") }, singleLine = true, modifier = Modifier.testTag("custom-service-name"))
                AtelierTextField(price, { price = it }, label = { Text("Price ($)") }, placeholder = { Text("0.00") }, singleLine = true, modifier = Modifier.testTag("custom-service-price"))
                error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = { TextButton(onClick = { cents?.let { onAdd(name.trim(), it) } }, enabled = !busy && name.isNotBlank() && cents != null, modifier = Modifier.testTag("custom-service-save")) { Text(if(busy) "Adding…" else "Add and select") } },
        dismissButton = { TextButton(onClick = onDismiss, enabled = !busy) { Text("Cancel") } })
}
