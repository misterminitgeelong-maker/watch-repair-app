package au.mainspring.nativeapp.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.NetworkMessagesViewModel
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NetworkMessagesScreen(onBack: () -> Unit, conversation: String? = null, initialTab: String? = null,
    network: String? = null, hub: String? = null, vm: NetworkMessagesViewModel = viewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val owner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    var query by rememberSaveable { mutableStateOf("") }
    var filterState by rememberSaveable { mutableStateOf("") }
    var filterRole by rememberSaveable { mutableStateOf("") }
    var pinnedOnly by rememberSaveable { mutableStateOf(false) }
    var announcementFilter by rememberSaveable { mutableStateOf("all") }
    var receiptAnnouncementId by remember { mutableStateOf<String?>(null) }
    var deleting by remember { mutableStateOf<NetworkPost?>(null) }
    var pendingFile by remember { mutableStateOf<ChatAttachment?>(null) }
    var networkMenu by remember { mutableStateOf(false) }
    val threadList = rememberLazyListState()
    val threadKey = "${s.network}/${s.hub ?: s.recipient ?: s.conversation.orEmpty()}"
    var displayedThread by remember { mutableStateOf("") }
    val displayedPosts = s.posts.filter { s.hub == null || !pinnedOnly || it.pinned }
    LaunchedEffect(s.tab, s.inThread, s.network) {
        if(!s.inThread) { displayedThread = ""; threadList.scrollToItem(0) }
    }
    LaunchedEffect(threadKey, s.posts.lastOrNull()?.id) {
        if(s.inThread && s.posts.isNotEmpty()) {
            val nearBottom = threadList.layoutInfo.visibleItemsInfo.lastOrNull()?.index?.let { it >= threadList.layoutInfo.totalItemsCount - 3 } != false
            if(displayedThread != threadKey || nearBottom || s.posts.last().mine) {
                val count = s.posts.count { s.hub == null || !pinnedOnly || it.pinned }
                threadList.scrollToItem((count - 1 + if(s.nextBefore != null) 1 else 0).coerceAtLeast(0))
            }
            displayedThread = threadKey
        }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { vm.addFiles(context.applicationContext, it) }
    val saveFile = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        val file = pendingFile; pendingFile = null
        if(uri != null && file != null) scope.launch { try { val bytes = vm.download(file); withContext(Dispatchers.IO) { context.contentResolver.openOutputStream(uri)?.use { it.write(bytes) } ?: error("Could not save file.") } } catch(e: Exception) { vm.error(e) } }
    }
    val saveReceipts = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/csv")) { uri ->
        val id = receiptAnnouncementId
        if(uri != null && id != null) scope.launch { try {
            withContext(Dispatchers.IO) {
                ApiClient.service(NetworkApi::class.java).receiptCsv(s.network, id).use { body -> context.contentResolver.openOutputStream(uri)?.use { output -> body.byteStream().copyTo(output) } ?: error("Could not save receipt report.") }
            }
        } catch(e: Exception) { vm.error(e) } }
    }
    LaunchedEffect(Unit) { vm.start(conversation, initialTab, network, hub) }
    LaunchedEffect(owner) { owner.lifecycle.repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) { while(true) { kotlinx.coroutines.delay(15_000); vm.refresh() } } }
    Scaffold(topBar = { AtelierTopAppBar(title = { Text(s.title) }, navigationIcon = { BackButton(onClick = { if(s.inThread) vm.closeThread() else onBack() }) }, actions = { TextButton(vm::refresh, enabled = !s.loading && !s.busy) { Text("Refresh") } }) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if(s.loading || s.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            s.error?.let { ErrorBanner(it, Modifier.padding(12.dp), onRetry = vm::refresh) }
            if(!s.inThread) {
                s.networks.firstOrNull { it.id == s.network }?.let { selected ->
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.weight(1f)) {
                            TextButton({ networkMenu = true }, enabled = s.networks.size > 1 && !s.busy, contentPadding = PaddingValues(vertical = 4.dp, horizontal = 0.dp)) {
                                Text(selected.name, maxLines = 1, overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurface, style = MaterialTheme.typography.labelLarge)
                                if(s.networks.size > 1) Text(" ▾", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            DropdownMenu(networkMenu, { networkMenu = false }) {
                                s.networks.forEach { item -> DropdownMenuItem(text = { Text(item.name) }, onClick = { networkMenu = false; vm.selectNetwork(item.id) }) }
                            }
                        }
                        selected.ownState?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
                ScrollableTabRow(listOf("chats", "directory", "announcements", "hubs").indexOf(s.tab).coerceAtLeast(0), edgePadding = 0.dp) {
                    listOf("chats" to "Chats", "directory" to "Directory", "announcements" to "Announcements", "hubs" to "State hubs").forEach { (key, label) -> Tab(s.tab == key, { vm.tab(key) }, modifier = Modifier.testTag("network-tab-$key"), text = { Text(label, maxLines = 1) }) }
                }
            } else {
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(if(s.hub != null) "Shared with participating shops in this state." else "Private to the two participating sites.", Modifier.weight(1f), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if(s.hub != null) FilterChip(pinnedOnly, { pinnedOnly = !pinnedOnly }, label = { Text("Pinned messages") })
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
            LazyColumn(Modifier.weight(1f).testTag("network-content"), state = threadList, contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(if(s.inThread) 8.dp else 4.dp)) {
                if(s.network.isBlank() && !s.loading) item { EmptyState("Your network is not connected yet", "Ask Support Office to check your shop’s network membership.") }
                else if(s.inThread) {
                    if(s.nextBefore != null) item { TextButton(vm::earlier, enabled = !s.loading && !s.busy) { Text("Load earlier messages") } }
                    if(s.posts.isEmpty() && !s.loading) item { Text("No messages yet.") }
                    itemsIndexed(displayedPosts, key = { _, post -> post.id }) { index, post ->
                        if(index == 0 || phoneChatDay(displayedPosts[index - 1].createdAt) != phoneChatDay(post.createdAt)) PhoneChatDayLabel(phoneChatDay(post.createdAt))
                        PhoneChatBubble(outgoing = post.mine, body = post.body, timestamp = phoneChatTime(post.createdAt),
                            sender = if(post.mine) null else listOfNotNull(post.senderName, post.shopName.takeIf { s.hub != null }).distinct().joinToString(" · ").ifBlank { null },
                            status = listOfNotNull("Pinned".takeIf { post.pinned }, (if(post.resolvedAt != null) "Stock request · resolved" else "Stock request · open").takeIf { post.kind == "stock_request" }).joinToString(" · ").ifBlank { null },
                            modifier = Modifier.testTag("network-post-${post.id}")) {
                            post.replyPreview?.let { Text("Reply to: $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                            post.attachments.forEach { file -> TextButton({ pendingFile = file; saveFile.launch(file.filename) }) { Text("${file.filename} · ${(file.size + 1023) / 1024} KB ↓") } }
                            if(s.hub != null) {
                                Row(Modifier.horizontalScroll(rememberScrollState())) {
                                    TextButton({ vm.reply(post) }, enabled = !s.busy) { Text("Reply") }
                                    if(post.canModerate) TextButton({ vm.updateHub(post, pinned = !post.pinned) }, enabled = !s.busy) { Text(if(post.pinned) "Unpin" else "Pin") }
                                    if(post.kind == "stock_request" && (post.mine || post.canModerate)) TextButton({ vm.updateHub(post, resolved = post.resolvedAt == null) }, enabled = !s.busy) { Text(if(post.resolvedAt == null) "Resolve" else "Reopen") }
                                    if(post.mine || post.canModerate) TextButton({ deleting = post }, enabled = !s.busy) { Text("Delete") }
                                }
                            }
                        }
                    }
                } else when(s.tab) {
                    "directory" -> {
                        item {
                            OutlinedTextField(query, { query = it }, label = { Text("Search shops, number or location") }, modifier = Modifier.fillMaxWidth())
                            Row(Modifier.horizontalScroll(rememberScrollState())) { (listOf("") + s.contacts.mapNotNull { it.state }.distinct().sorted()).forEach { code -> FilterChip(filterState == code, { filterState = code }, label = { Text(code.ifBlank { "All states" }) }) } }
                            Row(Modifier.horizontalScroll(rememberScrollState())) { listOf("" to "All sites", "retail" to "Retail", "operator" to "Mobile", "hq" to "Support Office").forEach { (key, label) -> FilterChip(filterRole == key, { filterRole = key }, label = { Text(label) }) } }
                        }
                        items(s.contacts.filter { c -> (filterState.isBlank() || c.state == filterState) && (filterRole.isBlank() || c.role == filterRole) && "${c.name} ${c.shopNumber.orEmpty()} ${c.state.orEmpty()}".contains(query, true) }
                            .sortedWith(compareBy<NetworkContact> { it.state != s.networks.firstOrNull { n -> n.id == s.network }?.ownState }.thenBy { it.name }), key = { it.tenantId }) { contact ->
                            NetworkChatRow(contact.name, listOfNotNull(contact.shopNumber, contact.state, when(contact.role) { "hq" -> "Support Office"; "operator" -> "Mobile"; else -> "Retail" }).joinToString(" · "),
                                onClick = { vm.openDirect(contact.tenantId, contact.name) }, enabled = !s.busy, action = "Message shop")
                        }
                    }
                    "announcements" -> {
                        item {
                            Row(Modifier.horizontalScroll(rememberScrollState())) {
                                listOf("all" to "All updates", "state" to "My state", "network" to "Network-wide", "unread" to "Unread").forEach { (key, label) -> FilterChip(announcementFilter == key, { announcementFilter = key }, label = { Text(label) }) }
                            }
                        }
                        if(s.announcements.isEmpty() && !s.loading) item { Text("No announcements yet.") }
                        items(s.announcements.filter { a -> when(announcementFilter) { "unread" -> !a.read; "network" -> a.state == null; "state" -> a.state == s.networks.firstOrNull { it.id == s.network }?.ownState; else -> true } }, key = { it.id }) { a ->
                            FlatPanel {
                                Text(a.title, style = MaterialTheme.typography.titleMedium)
                                Text("${a.category} · ${a.state ?: "Network"}${if(a.pinned) " · Pinned" else ""}", style = MaterialTheme.typography.labelMedium)
                                Text(a.body)
                                Text("${a.author} · ${formatShopDate(a.createdAt)}", style = MaterialTheme.typography.bodySmall)
                                if(!a.read) TextButton({ vm.receipt(a, false) }, enabled = !s.busy) { Text("Mark as read") }
                                if(a.requiresConfirmation) {
                                    if(a.confirmed) Text("Confirmed ✓") else Button({ vm.receipt(a, true) }, enabled = !s.busy, modifier = Modifier.testTag("network-confirm-${a.id}")) { Text("I have read and understood") }
                                }
                                a.state?.let { code -> s.hubs.firstOrNull { it.code == code && it.accessible }?.let { h -> TextButton({ vm.openHub(h) }, enabled = !s.busy) { Text("Open state hub") } } }
                                if(a.canViewReceipts) TextButton({ receiptAnnouncementId = a.id; vm.receipts(a) }) { Text("View receipts") }
                            }
                        }
                        if(s.moreAnnouncements) item { TextButton(vm::moreAnnouncements, enabled = !s.busy) { Text("Load more announcements") } }
                    }
                    "hubs" -> {
                        item { Text("Connect with shops in your state", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(vertical = 8.dp)) }
                        items(s.hubs.sortedByDescending { it.mine }, key = { it.code }) { h ->
                            NetworkChatRow(h.name, if(h.mine) "Your state hub" else if(h.accessible) "State conversation" else "For shops in this state", unread = h.unread,
                                onClick = { vm.openHub(h) }, enabled = h.accessible && !s.busy, modifier = Modifier.testTag("network-hub-${h.code}"), initials = h.code)
                        }
                    }
                    else -> {
                        item {
                            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                Text("Recent chats", Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                                TextButton({ vm.tab("directory") }, enabled = !s.busy) { Text("New message") }
                            }
                        }
                        if(s.conversations.isEmpty() && !s.loading) item { Text("Your private shop conversations will appear here.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(vertical = 12.dp)) }
                        items(s.conversations.sortedByDescending { it.lastAt }, key = { it.id }) { c ->
                            NetworkChatRow(c.otherName, c.lastBody?.takeIf { it.isNotBlank() } ?: "Start a conversation", timestamp = formatShopDate(c.lastAt).substringBefore(' '), unread = c.unread,
                                onClick = { vm.openDirect(c.otherTenantId, c.otherName, c.id) }, enabled = !s.busy, modifier = Modifier.testTag("network-conversation-${c.id}"))
                        }
                        item {
                            Row(Modifier.fillMaxWidth().padding(top = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text("State hubs", Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                                TextButton({ vm.tab("hubs") }, enabled = !s.busy) { Text("View all") }
                            }
                        }
                        items(s.hubs.filter { it.accessible && it.mine }, key = { "hub-${it.code}" }) { h ->
                            NetworkChatRow(h.name, "Your state conversation", unread = h.unread, initials = h.code,
                                onClick = { vm.openHub(h) }, enabled = !s.busy, modifier = Modifier.testTag("network-hub-${h.code}"))
                        }
                        item { TextButton({ vm.tab("directory") }) { Text("Find a shop to message") } }
                    }
                }
            }
            if(s.inThread) {
                val canPost = if(s.hub != null) s.hubs.firstOrNull { it.code == s.hub }?.canPost == true else s.networks.firstOrNull { it.id == s.network }?.canPost == true
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                Column(Modifier.fillMaxWidth().imePadding(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if(s.sendUnknown) Column(Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) { Text("Check the refreshed conversation for your earlier message.", style = MaterialTheme.typography.bodySmall); TextButton(vm::reviewedSend, enabled = s.historyChecked && !s.busy) { Text("I have reviewed the conversation") } }
                    s.reply?.let { Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) { Text("Reply: ${it.body.take(70)}", Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall); TextButton({ vm.reply(null) }) { Text("Cancel") } } }
                    s.files.forEachIndexed { index, file -> Row(Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) { Text(file.name, Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall); TextButton({ vm.removeFile(index) }, enabled = !s.busy) { Text("Remove") } } }
                    if(s.hub != null) Row(Modifier.padding(horizontal = 16.dp)) { FilterChip(s.kind == "stock_request", { vm.kind(if(s.kind == "stock_request") "message" else "stock_request") }, label = { Text("Stock request") }, enabled = !s.busy && canPost) }
                    PhoneChatComposer(draft = s.draft, onDraft = vm::draft, onSend = vm::send, enabled = !s.busy && canPost, sending = s.busy,
                        sendEnabled = canPost && !s.busy && !s.loading && !s.sendUnknown && (s.draft.isNotBlank() || s.files.isNotEmpty()),
                        placeholder = if(canPost) "Message…" else "This conversation is read only",
                        onAttach = { picker.launch(arrayOf("image/jpeg", "image/png", "image/webp", "application/pdf")) },
                        inputModifier = Modifier.testTag("network-draft"), sendModifier = Modifier.testTag("network-send"))
                }
            }
        }
    }
    deleting?.let { post -> AlertDialog(onDismissRequest = { deleting = null }, title = { Text("Delete message?") }, text = { Text(post.body) }, confirmButton = { TextButton({ deleting = null; vm.deleteHub(post) }) { Text("Delete") } }, dismissButton = { TextButton({ deleting = null }) { Text("Cancel") } }) }
    s.receipts?.let { report -> AlertDialog(onDismissRequest = vm::dismissReceipts, title = { Text("Announcement receipts") }, text = {
        val shops = report.getAsJsonArray("shops")
        LazyColumn { items(shops?.toList().orEmpty()) { row -> val shop = row.asJsonObject; Text("${shop.get("name")?.asString.orEmpty()} · ${if(shop.get("confirmed_at")?.isJsonNull == false) "Confirmed" else if(shop.get("read_at")?.isJsonNull == false) "Read" else "Unread"}", Modifier.padding(vertical = 6.dp)) } }
    }, confirmButton = { TextButton(vm::dismissReceipts) { Text("Close") } }, dismissButton = { TextButton({ saveReceipts.launch("announcement-receipts.csv") }) { Text("Export CSV") } }) }
}

/** A conversation is one compact, left-aligned tap target, like a phone inbox. */
@Composable
private fun NetworkChatRow(
    name: String, preview: String, onClick: () -> Unit, modifier: Modifier = Modifier,
    timestamp: String? = null, unread: Int = 0, enabled: Boolean = true,
    initials: String = name.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }.take(2).joinToString("") { it.take(1) },
    action: String? = null,
) {
    Column {
        Surface(onClick = onClick, enabled = enabled, modifier = modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface) {
            Row(Modifier.padding(vertical = 14.dp, horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Surface(Modifier.size(42.dp), shape = CircleShape, color = MaterialTheme.colorScheme.surfaceVariant) {
                    Box(contentAlignment = Alignment.Center) { Text(initials.uppercase().ifBlank { "?" }, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(name, style = MaterialTheme.typography.titleSmall, fontWeight = if(unread > 0) FontWeight.Bold else FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(preview, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    timestamp?.let { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    if(unread > 0) Badge { Text(if(unread > 99) "99+" else unread.toString()) }
                    else Text(action ?: "›", style = if(action == null) MaterialTheme.typography.titleMedium else MaterialTheme.typography.labelSmall, color = if(enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
    }
}
