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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CustomersViewModel

@Composable
fun CustomersScreen(
    onOpenCustomer: (String) -> Unit,
    viewModel: CustomersViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Column(
        Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = state.query,
                onValueChange = viewModel::setQuery,
                modifier = Modifier.weight(1f),
                singleLine = true,
                label = { Text("Search name") },
            )
            Button(onClick = { viewModel.refresh() }, enabled = !state.loading) {
                Text("Load")
            }
        }
        if (state.loading && state.customers.isEmpty()) {
            CircularProgressIndicator(Modifier.padding(24.dp))
        }
        state.error?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = 16.dp),
                style = MaterialTheme.typography.bodySmall,
            )
        }
        LazyColumn(
            contentPadding = PaddingValues(bottom = 88.dp),
            modifier = Modifier
                .fillMaxSize()
                .weight(1f, fill = true),
        ) {
            items(state.customers, key = { it.id }) { c ->
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clickable { onOpenCustomer(c.id) }
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                ) {
                    Text(c.fullName, style = MaterialTheme.typography.titleMedium)
                    c.email?.let { e -> Text(e, style = MaterialTheme.typography.bodySmall) }
                    c.phone?.let { p -> Text(p, style = MaterialTheme.typography.bodySmall) }
                }
                HorizontalDivider()
            }
        }
    }
}
