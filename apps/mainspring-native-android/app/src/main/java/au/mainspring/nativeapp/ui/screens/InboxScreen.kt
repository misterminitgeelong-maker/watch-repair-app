package au.mainspring.nativeapp.ui.screens

import androidx.compose.material3.*
import androidx.compose.foundation.layout.*
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.InboxViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InboxScreen(
    onBack: () -> Unit,
    viewModel: InboxViewModel = viewModel(),
    embedded: Boolean = false,
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Scaffold(
        contentWindowInsets = if(embedded) androidx.compose.foundation.layout.WindowInsets(0,0,0,0) else androidx.compose.material3.ScaffoldDefaults.contentWindowInsets,
        topBar = {
            if(!embedded) TopAppBar(
                title = { Text("Inbox", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
                actions = { TextButton(onClick = { viewModel.refresh() }, enabled = !state.loading, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") } },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            if (embedded) Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = { viewModel.refresh() }, enabled = !state.loading, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") }
            }
            if (state.loading && state.events.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(16.dp), onRetry = { viewModel.refresh() }) }
            if (!state.loading && state.error == null && state.events.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("You're all caught up", "Customer replies and booking activity will show up here.")
            LazyColumn(
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxSize().weight(1f, fill = true),
            ) {
                items(state.events, key = { it.id }) { ev ->
                    au.mainspring.nativeapp.ui.FlatPanel {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(au.mainspring.nativeapp.ui.statusLabel(ev.eventType), style = MaterialTheme.typography.titleMedium)
                            Text(au.mainspring.nativeapp.ui.formatShopDate(ev.createdAt).substringBefore(' '), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text(ev.eventSummary, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}
