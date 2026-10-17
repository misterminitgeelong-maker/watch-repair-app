package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.PricingViewModel
import au.mainspring.nativeapp.api.PricingRow
@Composable fun PricingPicker(onClose: () -> Unit, onSelect: (PricingRow) -> Unit) {
 val vm: PricingViewModel = viewModel(); val state by vm.state.collectAsStateWithLifecycle(); var search by rememberSaveable { mutableStateOf("") }
 Dialog(onDismissRequest = onClose) { Surface(shape = MaterialTheme.shapes.large) {
  Column(Modifier.fillMaxWidth().heightIn(max = 650.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
   Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text("Catalogue pricing", style = MaterialTheme.typography.titleLarge); TextButton(onClick = onClose) { Text("Close") } }
   Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
    state.categories.forEach { category -> au.mainspring.nativeapp.ui.AtelierChip(state.category == category, { vm.category(category) }, label = { Text(when(category) { "vehicle_key" -> "Vehicle keys"; "general_service" -> "Services"; else -> "Garage doors" }) }) }
   }
   if(state.category == "vehicle_key") {
    var expanded by remember { mutableStateOf(false) }
    Box { OutlinedButton(onClick = { expanded = true }) { Text(state.make.ifBlank { "Choose manufacturer" }) }
     DropdownMenu(expanded, { expanded = false }) { state.makes.forEach { make -> DropdownMenuItem(text = { Text(make) }, onClick = { expanded = false; vm.make(make) }) } }
    }
   }
   au.mainspring.nativeapp.ui.AtelierTextField(search, { search = it }, label = { Text("Find model or service") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
   if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth()); state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
   LazyColumn(Modifier.weight(1f, fill = false), verticalArrangement = Arrangement.spacedBy(8.dp)) {
    val rows = state.rows.filter { search.isBlank() || "${it.label()} ${it.description.orEmpty()} ${it.notes.orEmpty()}".contains(search,true) }
    if(rows.isEmpty() && !state.loading) item { Text("No catalogue prices match this view") }
    items(rows, key = { it.id }) { row -> OutlinedCard(onClick = { onSelect(row) }, modifier = Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) {
     Text(row.label(), style = MaterialTheme.typography.titleSmall); Text(row.price?.let { "$${it.setScale(2, java.math.RoundingMode.HALF_UP)} AUD" } ?: "Price after inspection")
     Text(if(row.callout) "Callout included" else "Callout not included")
     row.location?.let { Text(it) }; row.tool?.let { Text("Tool: $it") }; row.notes?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
    } } }
   }
  }
 } }
}
