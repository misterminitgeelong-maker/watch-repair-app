package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CustomerDetailViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerDetailScreen(
    customerId: String,
    onBack: () -> Unit,
) {
    val vm: CustomerDetailViewModel = viewModel(
        key = customerId,
        factory = CustomerDetailViewModel.factory(customerId),
    )
    val state by vm.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(state.customer?.fullName ?: "Customer") },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("Back")
                    }
                },
            )
        },
    ) { padding ->
        when {
            state.loading && state.customer == null -> {
                CircularProgressIndicator(Modifier.padding(padding).padding(24.dp))
            }
            state.error != null && state.customer == null -> {
                Text(
                    state.error ?: "",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(padding).padding(16.dp),
                )
            }
            state.customer != null -> {
                val c = state.customer!!
                Column(
                    Modifier
                        .padding(padding)
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp),
                ) {
                    DetailLine("Email", c.email)
                    DetailLine("Phone", c.phone)
                    DetailLine("Address", c.address)
                    DetailLine("Notes", c.notes)
                    Spacer(Modifier.height(8.dp))
                    Text("Created ${c.createdAt}", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun DetailLine(label: String, value: String?) {
    if (value.isNullOrBlank()) return
    Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
    Text(value, style = MaterialTheme.typography.bodyLarge)
    Spacer(Modifier.height(12.dp))
}
