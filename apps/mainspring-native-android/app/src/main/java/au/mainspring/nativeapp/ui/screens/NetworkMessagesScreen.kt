package au.mainspring.nativeapp.ui.screens

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
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
                if(s.networks.size > 1) Row(Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp)) { s.networks.forEach { FilterChip(s.network == it.id, { vm.selectNetwork(it.id) }, label = { Text(it.name) }, enabled = !s.busy) } }
                ScrollableTabRow(listOf("chats", "directory", "announcements", "hubs").indexOf(s.tab).coerceAtLeast(0)) {
                    listOf("chats" to "Chats", "directory" to "Shop directory", "announcements" to "Announcements", "hubs" to "State hubs").forEach { (key, label) -> Tab(s.tab == key, { vm.tab(key) }, text = { Text(label) }) }
                }
            }
            LazyColumn(Modifier.weight(1f).testTag("network-content"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if(s.network.isBlank() && !s.loading) item { EmptyState("Your network is not connected yet", "Ask Support Office to check your shop’s network membership.") }
                else if(s.inThread) {
                    item { Text(if(s.hub != null) "Shared with participating shops in this state." else "Private to the two participating sites.", style = MaterialTheme.typography.bodySmall) }
                    if(s.hub != null) item { FilterChip(pinnedOnly, { pinnedOnly = !pinnedOnly }, label = { Text("Pinned messages") }) }
                    if(s.nextBefore != null) item { TextButton(vm::earlier, enabled = !s.loading && !s.busy) { Text("Load earlier messages") } }
                    if(s.posts.isEmpty() && !s.loading) item { Text("No messages yet.") }
                    items(s.posts.filter { !pinnedOnly || it.pinned }, key = { it.id }) { post ->
                        FlatPanel {
                            Text(listOfNotNull(post.senderName, post.shopName).joinToString(" · "), style = MaterialTheme.typography.labelLarge)
                            Text(formatShopDate(post.createdAt), style = MaterialTheme.typography.bodySmall)
                            if(post.pinned) Text("Pinned", color = MaterialTheme.colorScheme.primary)
                            post.replyPreview?.let { Text("Reply to: $it", style = MaterialTheme.typography.bodySmall) }
                            if(post.kind == "stock_request") Text(if(post.resolvedAt != null) "Stock request · resolved" else "Stock request · open", style = MaterialTheme.typography.labelLarge)
                            Text(post.body, Modifier.testTag("network-post-${post.id}"))
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
                            FlatPanel { Text(contact.name, style = MaterialTheme.typography.titleMedium); Text(listOfNotNull(contact.shopNumber, contact.state, contact.role).joinToString(" · ")); TextButton({ vm.openDirect(contact.tenantId, contact.name) }) { Text("Message shop") } }
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
                    "hubs" -> items(s.hubs, key = { it.code }) { h -> FlatPanel { Text(h.name, style = MaterialTheme.typography.titleMedium); Text(if(h.mine) "Your state hub" else if(h.accessible) "State hub" else "For shops in this state"); TextButton({ vm.openHub(h) }, enabled = h.accessible) { Text(if(h.unread > 0) "Open · ${h.unread} unread" else "Open hub") } } }
                    else -> {
                        item { SectionLabel("STATE HUBS") }
                        items(s.hubs.filter { it.accessible }, key = { "hub-${it.code}" }) { h -> TextButton({ vm.openHub(h) }, Modifier.fillMaxWidth().testTag("network-hub-${h.code}")) { Text("# ${h.name}${if(h.unread > 0) " · ${h.unread} unread" else ""}") } }
                        item { SectionLabel("DIRECT MESSAGES") }
                        items(s.conversations, key = { it.id }) { c -> FlatPanel { Text(c.otherName, style = MaterialTheme.typography.titleMedium); c.lastBody?.let { Text(it) }; TextButton({ vm.openDirect(c.otherTenantId, c.otherName, c.id) }, modifier = Modifier.testTag("network-conversation-${c.id}")) { Text(if(c.unread > 0) "Open · ${c.unread} unread" else "Open conversation") } } }
                        item { TextButton({ vm.tab("directory") }) { Text("Find a shop to message") } }
                    }
                }
            }
            if(s.inThread) {
                val canPost = if(s.hub != null) s.hubs.firstOrNull { it.code == s.hub }?.canPost == true else s.networks.firstOrNull { it.id == s.network }?.canPost == true
                Column(Modifier.fillMaxWidth().padding(12.dp).imePadding(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    if(s.sendUnknown) { Text("Check the refreshed conversation for your earlier message."); TextButton(vm::reviewedSend, enabled = s.historyChecked && !s.busy) { Text("I have reviewed the conversation") } }
                    s.reply?.let { Row { Text("Reply: ${it.body.take(70)}", Modifier.weight(1f)); TextButton({ vm.reply(null) }) { Text("Cancel") } } }
                    s.files.forEachIndexed { index, file -> Row { Text(file.name, Modifier.weight(1f)); TextButton({ vm.removeFile(index) }, enabled = !s.busy) { Text("Remove") } } }
                    if(s.hub != null) Row { FilterChip(s.kind == "stock_request", { vm.kind(if(s.kind == "stock_request") "message" else "stock_request") }, label = { Text("Stock request") }, enabled = !s.busy && canPost) }
                    OutlinedTextField(s.draft, vm::draft, Modifier.fillMaxWidth().testTag("network-draft"), enabled = !s.busy && canPost, label = { Text(if(canPost) "Message" else "This conversation is read only") }, maxLines = 4)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        TextButton({ picker.launch(arrayOf("image/jpeg", "image/png", "image/webp", "application/pdf")) }, enabled = !s.busy && canPost) { Text("Attach photo / PDF") }
                        Button(vm::send, enabled = canPost && !s.busy && !s.loading && !s.sendUnknown && (s.draft.isNotBlank() || s.files.isNotEmpty()), modifier = Modifier.testTag("network-send")) { Text("Send") }
                    }
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
