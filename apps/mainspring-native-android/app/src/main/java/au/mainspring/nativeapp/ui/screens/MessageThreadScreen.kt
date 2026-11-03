package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.consumeWindowInsets
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.MessageThreadViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.formatShopDate
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MessageThreadScreen(resource: String, jobId: String, onBack: () -> Unit,
    vm: MessageThreadViewModel = viewModel(key = "$resource/$jobId", factory = MessageThreadViewModel.factory(resource, jobId)), embedded: Boolean = false) {
    val state by vm.state.collectAsStateWithLifecycle()
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(lifecycle, vm) { lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) { while(isActive) { vm.refresh(); delay(15_000) } } }
    Scaffold(contentWindowInsets = if(embedded) WindowInsets(0,0,0,0) else ScaffoldDefaults.contentWindowInsets, topBar = { if(!embedded) au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Customer conversation") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
        actions = { TextButton(onClick = vm::refresh, enabled = !state.loading) { Text("Refresh") } }) }) { padding ->
        Column(Modifier.padding(padding).consumeWindowInsets(padding).fillMaxSize().imePadding().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if(state.loading && state.messages.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            if(state.uncertain) OutlinedButton(onClick = vm::acknowledgeHistory, enabled = !state.loading && state.historyChecked) { Text("I checked the conversation") }
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if(state.messages.isEmpty() && !state.loading) item { Text("No messages yet") }
                items(state.messages, key = { it.id }) { message ->
                    val mine = message.direction != "inbound"
                    Surface(Modifier.fillMaxWidth().padding(start = if(mine) 32.dp else 0.dp, end = if(mine) 0.dp else 32.dp), shape = MaterialTheme.shapes.medium,
                        color = if(mine) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.surface,
                        contentColor = if(mine) MaterialTheme.colorScheme.onSecondary else MaterialTheme.colorScheme.onSurface) {
                        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(when(message.direction) { "inbound" -> "Customer"; "system" -> "Automatic notification"; else -> "Shop" }, style = MaterialTheme.typography.labelLarge)
                            Text(message.body)
                            Text(formatShopDate(message.createdAt, TokenStore.calendarTimezone()), style = MaterialTheme.typography.bodySmall)
                            message.status?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                        }
                    }
                }
            }
            au.mainspring.nativeapp.ui.AtelierTextField(state.draft, vm::setDraft, label = { Text("Message to customer") }, modifier = Modifier.fillMaxWidth(), enabled = !state.sending, maxLines = 4)
            Button(onClick = vm::send, enabled = !state.sending && !state.uncertain && state.draft.isNotBlank(), modifier = Modifier.fillMaxWidth()) { Text(if(state.sending) "Sending…" else "Send to customer") }
        }
    }
}
