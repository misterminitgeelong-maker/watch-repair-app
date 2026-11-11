package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.consumeWindowInsets
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.MessageThreadViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.*
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
        Column(Modifier.padding(padding).consumeWindowInsets(padding).fillMaxSize().imePadding()) {
            if(state.loading && state.messages.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            if(state.uncertain) OutlinedButton(onClick = vm::acknowledgeHistory, enabled = !state.loading && state.historyChecked) { Text("I checked the conversation") }
            val newestFirst = state.messages.asReversed()
            LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("customer-chat-history"), reverseLayout = true,
                contentPadding = PaddingValues(horizontal = 14.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if(state.messages.isEmpty() && !state.loading) item { EmptyState("No messages yet", "Your conversation with this customer will appear here.") }
                itemsIndexed(newestFirst, key = { _, message -> message.id }) { index, message ->
                    val mine = message.direction != "inbound"
                    Column {
                        val day = phoneChatDay(message.createdAt)
                        if(index == newestFirst.lastIndex || phoneChatDay(newestFirst[index + 1].createdAt) != day) PhoneChatDayLabel(day)
                        PhoneChatBubble(mine, message.body, phoneChatTime(message.createdAt),
                            sender = when(message.direction) { "inbound" -> "Customer"; "system" -> "Automatic notification"; else -> null },
                            status = message.status, modifier = Modifier.testTag("customer-message-${message.id}"))
                    }
                }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            PhoneChatComposer(state.draft, vm::setDraft, vm::send, enabled = !state.sending,
                sending = state.sending, placeholder = "Message to customer", sendDescription = "Send to customer",
                inputModifier = Modifier.testTag("customer-chat-draft"), sendModifier = Modifier.testTag("customer-chat-send"),
                sendEnabled = !state.uncertain && state.draft.isNotBlank())
        }
    }
}
