package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.PricingRow
import au.mainspring.nativeapp.ui.*

@Composable fun MobileIntakePricingDialog(close: () -> Unit, choose: (PricingRow, String, String) -> Unit, vm: PricingViewModel = viewModel(key = "intake-pricing")) {
    val s by vm.state.collectAsStateWithLifecycle()
    var query by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf<PricingRow?>(null) }
    var price by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(onDismissRequest = close, title = { Text("Pricing catalogue") }, text = {
        Column(Modifier.heightIn(max = 520.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.horizontalScroll(rememberScrollState())) { s.categories.forEach { category -> FilterChip(s.category == category, { selected = null; vm.category(category) }, label = { Text(when(category) { "vehicle_key" -> "Vehicle keys"; "garage_door" -> "Garage doors"; else -> "General services" }) }) } }
            OutlinedTextField(query, { query = it }, label = { Text("Search make or service") })
            if(s.category == "vehicle_key") Row(Modifier.horizontalScroll(rememberScrollState())) { s.makes.filter { it.contains(query, true) }.forEach { make -> FilterChip(s.make == make, { selected = null; vm.make(make) }, label = { Text(make) }) } }
            if(s.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            s.error?.let { ErrorBanner(it, onRetry = vm::loadRows) }
            LazyColumn(Modifier.weight(1f, fill = false)) { items(s.rows.filter { s.category == "vehicle_key" || it.label().contains(query, true) }, key = { it.id }) { row ->
                TextButton({ selected = row; price = row.price?.setScale(2, java.math.RoundingMode.HALF_UP)?.toPlainString().orEmpty() }, Modifier.fillMaxWidth()) { Text("${if(selected?.id == row.id) "✓ " else ""}${row.label()} · ${row.price?.let { "$${it.toPlainString()}" } ?: "POA"}${if(row.callout) " · Callout included" else ""}") }
            } }
            if(selected != null) OutlinedTextField(price, { price = it }, label = { Text("Agreed customer price ($)") })
            error?.let { ErrorBanner(it) }
        }
    }, confirmButton = { TextButton({ try { dollarsToCentsChecked(price); require(price.isNotBlank()) { "Enter the agreed price." }; selected?.let { choose(it, s.category, price) } } catch(e: Exception) { error = e.userMessage() } }, enabled = selected != null) { Text("Use price") } }, dismissButton = { TextButton(close) { Text("Cancel") } })
}
