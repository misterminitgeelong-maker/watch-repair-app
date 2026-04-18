package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.InvoicesViewModel
import au.mainspring.nativeapp.ui.formatCents

@Composable
fun InvoicesScreen(
    onOpenInvoice: (String) -> Unit,
    viewModel: InvoicesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.End) {
            Button(onClick = { viewModel.refresh() }, enabled = !state.loading) { Text("Refresh") }
        }
        if (state.loading && state.invoices.isEmpty()) {
            CircularProgressIndicator(Modifier.padding(24.dp))
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp)) }
        LazyColumn(
            contentPadding = PaddingValues(bottom = 96.dp),
            modifier = Modifier.fillMaxSize().weight(1f, fill = true),
        ) {
            items(state.invoices, key = { it.id }) { inv ->
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clickable { onOpenInvoice(inv.id) }
                        .padding(16.dp),
                ) {
                    Text("${inv.invoiceNumber} · ${inv.status}", style = MaterialTheme.typography.titleMedium)
                    Text(formatCents(inv.totalCents, inv.currency), style = MaterialTheme.typography.bodyLarge)
                }
                HorizontalDivider()
            }
        }
    }
}
