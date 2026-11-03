package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.DEFAULT_WEBHOOK_EVENTS
import au.mainspring.nativeapp.IntegrationsViewModel
import au.mainspring.nativeapp.ui.*

/** Shop API keys and outbound webhooks, mirroring the web Settings "Notifications & integrations" cards. */
@Composable fun IntegrationsScreen(onBack: () -> Unit, viewModel: IntegrationsViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var keyName by rememberSaveable { mutableStateOf("") }
    var hookUrl by rememberSaveable { mutableStateOf("") }
    var hookEvents by rememberSaveable { mutableStateOf(DEFAULT_WEBHOOK_EVENTS) }
    var revokeId by remember { mutableStateOf<String?>(null) }
    var removeId by remember { mutableStateOf<String?>(null) }
    val enabled = state.allowed && !state.busy
    Scaffold(topBar = { BackLargeHeader("More", "Shop", "API keys & webhooks", onBack) }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).testTag("integrations"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if(state.loading || state.busy) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            state.error?.let { item { ErrorBanner(it, onRetry = viewModel::refresh, modifier = Modifier.testTag("integrations-error")) } }
            state.info?.let { item { Text(it, Modifier.testTag("integrations-info"), style = MaterialTheme.typography.bodyMedium) } }
            if(!state.allowed) item { Text("Only managers and owners can create or remove keys and webhooks.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }

            item { SectionLabel("API keys") }
            item { Text("Keys let your own software talk to this shop. The full key is shown once when you create it.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            if(state.allowed) item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    AtelierTextField(keyName, { keyName = it }, Modifier.weight(1f).testTag("api-key-name"), enabled = enabled, label = { Text("Key name") }, singleLine = true)
                    SecondaryAction({ viewModel.createKey(keyName); keyName = "" }, Modifier.heightIn(min = 52.dp).testTag("api-key-create"), enabled = enabled && keyName.isNotBlank()) { Text("Create") }
                }
            }
            state.createdKey?.let { created ->
                item(key = "created-${created.id}") {
                    FlatPanel(Modifier.testTag("api-key-created")) {
                        Text("Copy this key now (${created.name})", style = MaterialTheme.typography.titleSmall)
                        SelectionContainer { Text(created.apiKey, Modifier.testTag("api-key-secret"), style = MaterialTheme.typography.bodyMedium, fontFamily = FontFamily.Monospace) }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            SecondaryAction({
                                (context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager)
                                    .setPrimaryClip(android.content.ClipData.newPlainText("API key", created.apiKey))
                                android.widget.Toast.makeText(context, "API key copied", android.widget.Toast.LENGTH_SHORT).show()
                            }, Modifier.heightIn(min = 48.dp).testTag("api-key-copy")) { Text("Copy key") }
                            TextButton(viewModel::dismissCreatedKey, Modifier.heightIn(min = 48.dp).testTag("api-key-dismiss")) { Text("I have saved it") }
                        }
                    }
                }
            }
            if(state.keys.isEmpty() && !state.loading) item { Text("No API keys yet.", style = MaterialTheme.typography.bodySmall) }
            items(state.keys, key = { "key-${it.id}" }) { key ->
                FlatPanel(Modifier.testTag("api-key-${key.id}")) {
                    DetailRow(key.name, "${key.keyPrefix}…")
                    if(state.allowed) TextButton({ revokeId = key.id }, Modifier.heightIn(min = 48.dp).testTag("api-key-revoke-${key.id}"), enabled = enabled,
                        colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Revoke") }
                }
            }

            item { SectionLabel("Outbound webhooks") }
            item { Text("We send a signed message to your address when these events happen. Use * to receive every event. Addresses must start with https://.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            if(state.allowed) item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    AtelierTextField(hookUrl, { hookUrl = it }, Modifier.fillMaxWidth().testTag("webhook-url"), enabled = enabled, label = { Text("Address (https://…)") }, singleLine = true,
                        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Uri))
                    AtelierTextField(hookEvents, { hookEvents = it }, Modifier.fillMaxWidth().testTag("webhook-events"), enabled = enabled, label = { Text("Events, comma separated") }, singleLine = true)
                    PrimaryAction({ viewModel.addWebhook(hookUrl, hookEvents); hookUrl = "" }, Modifier.fillMaxWidth().heightIn(min = 52.dp).testTag("webhook-add"), enabled = enabled && hookUrl.isNotBlank()) { Text("Add webhook") }
                }
            }
            if(state.webhooks.isEmpty() && !state.loading) item { Text("No webhooks yet.", style = MaterialTheme.typography.bodySmall) }
            items(state.webhooks, key = { "hook-${it.id}" }) { hook ->
                FlatPanel(Modifier.testTag("webhook-${hook.id}")) {
                    Text(hook.url, style = MaterialTheme.typography.bodyMedium)
                    Text("Events: ${hook.eventTypes.ifBlank { "none" }}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if(state.allowed) TextButton({ removeId = hook.id }, Modifier.heightIn(min = 48.dp).testTag("webhook-remove-${hook.id}"), enabled = enabled,
                        colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("Remove") }
                }
            }
        }
    }
    revokeId?.let { id ->
        val key = state.keys.firstOrNull { it.id == id }
        AlertDialog(onDismissRequest = { revokeId = null }, title = { Text("Revoke this key?") },
            text = { Text("${key?.name ?: "This key"} stops working straight away. Anything using it will be refused.") },
            confirmButton = { TextButton({ revokeId = null; viewModel.revokeKey(id) }, Modifier.testTag("api-key-revoke-confirm")) { Text("Revoke") } },
            dismissButton = { TextButton({ revokeId = null }) { Text("Cancel") } })
    }
    removeId?.let { id ->
        val hook = state.webhooks.firstOrNull { it.id == id }
        AlertDialog(onDismissRequest = { removeId = null }, title = { Text("Remove this webhook?") },
            text = { Text("${hook?.url ?: "This address"} will stop receiving events.") },
            confirmButton = { TextButton({ removeId = null; viewModel.removeWebhook(id) }, Modifier.testTag("webhook-remove-confirm")) { Text("Remove") } },
            dismissButton = { TextButton({ removeId = null }) { Text("Cancel") } })
    }
}
