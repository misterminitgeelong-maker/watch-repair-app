package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import au.mainspring.nativeapp.api.ShoeCatalogueItem
import au.mainspring.nativeapp.api.ShoeItemCreate
import au.mainspring.nativeapp.api.ShoeJobItemRead
import au.mainspring.nativeapp.api.ShoeRead
import au.mainspring.nativeapp.ui.*

private fun ShoeRead.summary(): String =
    listOfNotNull(shoeType, brand, color).filter { it.isNotBlank() }.joinToString(" · ").ifBlank { "Shoe details not recorded" }

/** One pair: type, brand, colour and condition notes. [onRemove] is null for the job's primary pair. */
@Composable
fun ShoePairCard(index: Int, shoe: ShoeRead?, onRemove: (() -> Unit)?, enabled: Boolean) {
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(if(index == 1) "PRIMARY PAIR" else "PAIR $index", style = MaterialTheme.typography.labelMedium, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(shoe?.summary() ?: "Shoe details not recorded", style = MaterialTheme.typography.bodyLarge)
                shoe?.notes?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            if(onRemove != null) TextButton(onClick = onRemove, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp)) { Text("Remove") }
        }
    }
}

/** A service line with its price and quantity. */
@Composable
fun ShoeServiceRow(item: ShoeJobItemRead, currency: String, onRemove: () -> Unit, enabled: Boolean) {
    FlatPanel {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(item.name, style = MaterialTheme.typography.titleMedium)
                val qty = if(item.quantity == 1.0) "" else "×${item.quantity.toString().removeSuffix(".0")} "
                Text(qty + (item.price?.let { formatCents((it * item.quantity).toInt(), currency) } ?: "Price after inspection"),
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                item.notes?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            TextButton(onClick = onRemove, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp)) { Text("Remove") }
        }
    }
}

/** Pick one or more services from the shoe catalogue (same list the intake wizard uses). */
@Composable
fun ShoeServicePickerDialog(catalogue: List<ShoeCatalogueItem>, currency: String, busy: Boolean, onClose: () -> Unit, onAdd: (List<ShoeItemCreate>) -> Unit) {
    var search by rememberSaveable { mutableStateOf("") }
    var picked by remember { mutableStateOf(setOf<String>()) }
    Dialog(onDismissRequest = onClose) {
        Surface(shape = MaterialTheme.shapes.large) {
            Column(Modifier.fillMaxWidth().heightIn(max = 650.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("Add services", style = MaterialTheme.typography.titleLarge)
                    TextButton(onClick = onClose) { Text("Close") }
                }
                AtelierTextField(search, { search = it }, label = { Text("Search repair catalogue") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                if(catalogue.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
                LazyColumn(Modifier.weight(1f, fill = false), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(catalogue.filter { it.key in picked || search.isBlank() || it.name.contains(search, true) }.take(60), key = { it.key }) { item ->
                        SelectableCard(selected = item.key in picked, onClick = { picked = if(item.key in picked) picked - item.key else picked + item.key }) {
                            Text(item.name, style = MaterialTheme.typography.titleMedium)
                            Text(item.priceCents?.let { formatCents(it, currency) } ?: "Inspection quote", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                PrimaryAction(onClick = {
                    onAdd(catalogue.filter { it.key in picked }.map { ShoeItemCreate(it.key, it.groupId, it.name, it.pricingType, it.priceCents, 1.0) })
                }, enabled = picked.isNotEmpty() && !busy, modifier = Modifier.fillMaxWidth()) { Text(if(busy) "Adding…" else "Add ${picked.size} service${if(picked.size == 1) "" else "s"}") }
            }
        }
    }
}

@Composable
fun AddPairDialog(busy: Boolean, onClose: () -> Unit, onAdd: (type: String, brand: String, colour: String, notes: String) -> Unit) {
    var type by rememberSaveable { mutableStateOf("") }
    var brand by rememberSaveable { mutableStateOf("") }
    var colour by rememberSaveable { mutableStateOf("") }
    var notes by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onClose, title = { Text("Add pair") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                AtelierTextField(type, { type = it }, label = { Text("Shoe type") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                AtelierTextField(brand, { brand = it }, label = { Text("Brand") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                AtelierTextField(colour, { colour = it }, label = { Text("Colour") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                AtelierTextField(notes, { notes = it }, label = { Text("Condition notes") }, modifier = Modifier.fillMaxWidth(), singleLine = false, maxLines = 3)
            }
        },
        confirmButton = { PrimaryAction(onClick = { onAdd(type, brand, colour, notes); onClose() }, enabled = !busy) { Text("Add pair") } },
        dismissButton = { TextButton(onClick = onClose) { Text("Cancel") } },
    )
}
