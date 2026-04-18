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
import au.mainspring.nativeapp.QuotesViewModel
import au.mainspring.nativeapp.ui.formatCents

@Composable
fun QuotesScreen(
    onOpenQuote: (String) -> Unit,
    viewModel: QuotesViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally) {
        Row(Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.End) {
            Button(onClick = { viewModel.refresh() }, enabled = !state.loading) { Text("Refresh") }
        }
        if (state.loading && state.quotes.isEmpty()) {
            CircularProgressIndicator(Modifier.padding(24.dp))
        }
        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(16.dp))
        }
        LazyColumn(
            contentPadding = PaddingValues(bottom = 96.dp),
            modifier = Modifier.fillMaxSize().weight(1f, fill = true),
        ) {
            items(state.quotes, key = { it.id }) { q ->
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clickable { onOpenQuote(q.id) }
                        .padding(16.dp),
                ) {
                    Text("${q.status.uppercase()} · ${formatCents(q.totalCents, q.currency)}", style = MaterialTheme.typography.titleMedium)
                    Text("Job ${q.repairJobId}", style = MaterialTheme.typography.bodySmall)
                    Text(q.createdAt, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                HorizontalDivider()
            }
        }
    }
}
