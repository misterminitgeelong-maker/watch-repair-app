package au.mainspring.nativeapp

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

data class ChatFile(val name: String, val mime: String, val bytes: ByteArray)
data class NetworkMessagesState(
    val loading: Boolean = false, val busy: Boolean = false, val error: String? = null, val info: String? = null,
    val networks: List<MessagingNetwork> = emptyList(), val network: String = "", val tab: String = "chats",
    val hubs: List<StateHub> = emptyList(), val contacts: List<NetworkContact> = emptyList(),
    val conversations: List<NetworkConversation> = emptyList(), val posts: List<NetworkPost> = emptyList(),
    val hub: String? = null, val conversation: String? = null, val recipient: String? = null, val title: String = "Messages",
    val nextBefore: String? = null, val announcements: List<NetworkAnnouncement> = emptyList(), val moreAnnouncements: Boolean = false,
    val draft: String = "", val files: List<ChatFile> = emptyList(), val reply: NetworkPost? = null, val kind: String = "message",
    val receipts: JsonObject? = null,
    val sendUnknown: Boolean = false, val historyChecked: Boolean = false,
    val historyPages: Int = 1,
) { val inThread get() = hub != null || recipient != null || conversation != null }

class NetworkMessagesViewModel(private val api: NetworkApi = ApiClient.service(NetworkApi::class.java)) : ViewModel() {
    private val mutable = MutableStateFlow(NetworkMessagesState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    private var targetGeneration = 0L
    private val drafts = TokenStore.bindDrafts()
    private fun draftKey(s: NetworkMessagesState = mutable.value) = "network/${s.network}/${s.hub ?: s.recipient ?: s.conversation ?: ""}"
    fun start(conversation: String? = null, tab: String? = null, network: String? = null, hub: String? = null) {
        if(mutable.value.networks.isNotEmpty()) return
        request = viewModelScope.launch {
            mutable.update { it.copy(loading = true, error = null) }
            try {
                val networks = api.networks()
                val linked = conversation?.let { id -> api.conversations().firstOrNull { it.id == id } }
                if(conversation != null && linked == null) error("This conversation is unavailable for your current shop.")
                val selected = networks.firstOrNull { it.id == (network ?: linked?.networkId) } ?: networks.firstOrNull()
                mutable.update { it.copy(networks = networks, network = selected?.id.orEmpty(), tab = tab ?: "chats", loading = false) }
                if(selected != null) {
                    refreshData()
                    if(linked != null) openDirect(linked.otherTenantId, linked.otherName, linked.id)
                    else if(hub != null) mutable.value.hubs.firstOrNull { it.code == hub && it.accessible }?.let { openHub(it) }
                }
            } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun selectNetwork(id: String) { if(mutable.value.busy) return; closeThread(); request?.cancel(); targetGeneration++; mutable.update { it.copy(network = id, posts = emptyList(), contacts = emptyList(), hubs = emptyList(), conversations = emptyList(), announcements = emptyList()) }; refresh() }
    fun tab(value: String) { if(mutable.value.busy) return; closeThread(); mutable.update { it.copy(tab = value) }; refresh() }
    fun refresh() { if(mutable.value.busy || mutable.value.loading) return; if(mutable.value.network.isBlank()) { start(); return }; request?.cancel(); request = viewModelScope.launch { refreshData() } }
    private suspend fun refreshData() {
        val s = mutable.value; if(s.network.isBlank()) return
        val generation = targetGeneration
        mutable.update { it.copy(loading = true, error = null) }
        try {
            val hubs = api.hubs(s.network); val conversations = api.conversations(s.network)
            val contacts = api.contacts(s.network)
            val announcements = if(s.tab == "announcements") {
                var page = api.announcements(s.network)
                val rows = page.announcements.toMutableList()
                while(page.hasMore && rows.size < s.announcements.size) { page = api.announcements(s.network, rows.size); rows += page.announcements }
                AnnouncementPage(rows, page.hasMore)
            } else null
            val page = s.hub?.let { code ->
                var current = api.hubMessages(s.network, code)
                val rows = current.messages.toMutableList()
                repeat((s.historyPages - 1).coerceAtLeast(0)) {
                    current.nextBefore?.let { before -> current = api.hubMessages(s.network, code, before); rows.addAll(0, current.messages) }
                }
                HubPage(rows.distinctBy { it.id }, current.nextBefore)
            }
            val conversation = s.conversation ?: s.recipient?.let { recipient -> conversations.firstOrNull { it.otherTenantId == recipient }?.id }
            val posts = page?.messages ?: conversation?.let { api.directMessages(it) }
            if(generation != targetGeneration) return
            mutable.update { it.copy(loading = false, hubs = hubs, contacts = contacts, conversations = conversations,
                posts = posts ?: it.posts, nextBefore = page?.nextBefore, conversation = conversation, historyChecked = true,
                announcements = announcements?.announcements ?: it.announcements, moreAnnouncements = announcements?.hasMore ?: it.moreAnnouncements) }
            if(page != null) markHubRead(s.network, s.hub!!, page.messages.lastOrNull()?.id)
            refreshCounts()
        } catch(e: CancellationException) { throw e } catch(e: Exception) { if(generation == targetGeneration) mutable.update { it.copy(loading = false, error = e.userMessage()) } }
    }
    private suspend fun markHubRead(network: String, hub: String, id: String?) {
        if(id == null) return
        val response = api.readHub(network, hub, JsonObject().apply { addProperty("message_id", id) })
        if(!response.isSuccessful) throw retrofit2.HttpException(response)
    }
    fun openHub(h: StateHub) { if(!h.accessible || mutable.value.busy) return; closeThread(); mutable.update { it.copy(hub = h.code, title = h.name, tab = "chats") }; loadDraft(); refresh() }
    fun openDirect(tenant: String, name: String, id: String? = null) { if(mutable.value.busy) return; closeThread(); mutable.update { it.copy(recipient = tenant, conversation = id ?: it.conversations.firstOrNull { c -> c.otherTenantId == tenant }?.id, title = name, tab = "chats") }; loadDraft(); refresh() }
    fun closeThread() { if(mutable.value.busy) return; request?.cancel(); targetGeneration++; mutable.update { it.copy(hub = null, conversation = null, recipient = null, title = "Messages", posts = emptyList(), files = emptyList(), draft = "", reply = null, nextBefore = null, loading = false, sendUnknown = false, historyChecked = false, historyPages = 1) } }
    private fun loadDraft() { mutable.update { it.copy(draft = drafts.loadMessageDraft(draftKey(it)), sendUnknown = drafts.pendingOperation("send/${draftKey(it)}")) } }
    fun reviewedSend() { if(mutable.value.historyChecked && !mutable.value.busy && drafts.setPendingOperation("send/${draftKey()}", false)) mutable.update { it.copy(sendUnknown = false, error = null) } }
    fun draft(value: String) { if(value.length <= 2000) { mutable.update { it.copy(draft = value) }; drafts.saveMessageDraft(draftKey(), value) } }
    fun reply(post: NetworkPost?) { mutable.update { it.copy(reply = post) } }
    fun kind(value: String) { mutable.update { it.copy(kind = value) } }
    fun removeFile(index: Int) { mutable.update { it.copy(files = it.files.filterIndexed { i, _ -> i != index }) } }
    fun addFiles(context: Context, uris: List<Uri>) {
        if(mutable.value.busy) return
        if(uris.size + mutable.value.files.size > 5) { error(IllegalArgumentException("Attach up to five files.")); return }
        val generation = targetGeneration
        viewModelScope.launch {
            try {
                val files = withContext(Dispatchers.IO) { uris.map { uri ->
                    val mime = context.contentResolver.getType(uri).orEmpty()
                    require(mime in setOf("image/jpeg", "image/png", "image/webp", "application/pdf")) { "Attach a JPEG, PNG, WebP photo or PDF." }
                    val name = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c -> if(c.moveToFirst()) c.getString(0) else null } ?: "attachment"
                    val bytes = context.contentResolver.openInputStream(uri)?.use { input -> val output = java.io.ByteArrayOutputStream(); val buffer = ByteArray(8192); while(output.size() <= 5 * 1024 * 1024) { val count = input.read(buffer, 0, minOf(buffer.size, 5 * 1024 * 1024 + 1 - output.size())); if(count < 0) break; output.write(buffer, 0, count) }; output.toByteArray() } ?: error("Could not read file.")
                    require(bytes.size <= 5 * 1024 * 1024) { "Each file must be 5 MB or smaller." }
                    ChatFile(name.replace(Regex("[\\r\\n\"]"), "_"), mime, bytes)
                } }
                if(generation != targetGeneration) return@launch
                require(mutable.value.files.size + files.size <= 5 && (mutable.value.files + files).sumOf { it.bytes.size.toLong() } <= 10 * 1024 * 1024) { "Attach up to five files, 10 MB total." }
                mutable.update { it.copy(files = it.files + files, error = null) }
            } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
        }
    }
    private fun act(block: suspend () -> Unit) {
        if(mutable.value.busy || mutable.value.loading) return
        mutable.update { it.copy(busy = true, error = null, info = null) }
        viewModelScope.launch { try { block() } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } } finally { mutable.update { it.copy(busy = false) } } }
    }
    fun send() {
        val s = mutable.value
        if(!s.inThread || s.sendUnknown || (s.draft.isBlank() && s.files.isEmpty())) return
        act {
            val pending = "send/${draftKey(s)}"
            check(drafts.setPendingOperation(pending, true)) { "Could not save the message checkpoint. Check device storage before sending." }
            try {
            val text = s.draft.trim().toRequestBody("text/plain".toMediaType())
            val files = s.files.map { MultipartBody.Part.createFormData("files", it.name, it.bytes.toRequestBody(it.mime.toMediaType())) }
            val sent = if(s.hub != null) api.sendHub(s.network, s.hub, text, s.kind.toRequestBody("text/plain".toMediaType()), s.reply?.id?.toRequestBody("text/plain".toMediaType()), files)
                else api.sendDirect(s.network, requireNotNull(s.recipient), text, files)
            drafts.saveMessageDraft(draftKey(s), "")
            drafts.setPendingOperation(pending, false)
            mutable.update { it.copy(draft = "", files = emptyList(), reply = null, kind = "message", conversation = sent.conversationId ?: it.conversation, posts = (it.posts + sent).distinctBy { p -> p.id }) }
            refreshCounts()
            } catch(e: CancellationException) { throw e } catch(e: Exception) {
                val definite = e is retrofit2.HttpException && e.code() in 400..499
                if(definite) drafts.setPendingOperation(pending, false)
                mutable.update { it.copy(sendUnknown = !definite, historyChecked = false, error = if(definite) e.userMessage() else "Delivery is uncertain. Refresh and check the conversation before sending again. ${e.userMessage()}") }
            }
        }
    }
    fun earlier() { val s = mutable.value; val before = s.nextBefore ?: return; act { val page = api.hubMessages(s.network, s.hub ?: return@act, before); mutable.update { it.copy(posts = (page.messages + it.posts).distinctBy { p -> p.id }, nextBefore = page.nextBefore, historyPages = it.historyPages + 1) } } }
    fun moreAnnouncements() { val s = mutable.value; act { val page = api.announcements(s.network, s.announcements.size); mutable.update { it.copy(announcements = (it.announcements + page.announcements).distinctBy { a -> a.id }, moreAnnouncements = page.hasMore) } } }
    fun receipt(a: NetworkAnnouncement, confirm: Boolean) = act { val updated = api.receipt(mutable.value.network, a.id, JsonObject().apply { addProperty("confirm", confirm) }); mutable.update { it.copy(announcements = it.announcements.map { old -> if(old.id == a.id) updated else old }) }; refreshCounts() }
    fun receipts(a: NetworkAnnouncement) = act { val report = api.receipts(mutable.value.network, a.id); mutable.update { it.copy(receipts = report) } }
    fun dismissReceipts() { mutable.update { it.copy(receipts = null) } }
    fun updateHub(post: NetworkPost, pinned: Boolean? = null, resolved: Boolean? = null) = act {
        val s = mutable.value; val hub = s.hub ?: return@act
        val updated = api.updateHub(s.network, hub, post.id, JsonObject().apply { pinned?.let { addProperty("pinned", it) }; resolved?.let { addProperty("resolved", it) } })
        mutable.update { it.copy(posts = it.posts.map { old -> if(old.id == post.id) updated else old }) }
    }
    fun deleteHub(post: NetworkPost) = act { val s = mutable.value; val response = api.deleteHub(s.network, s.hub ?: return@act, post.id); if(!response.isSuccessful) throw retrofit2.HttpException(response); mutable.update { it.copy(posts = it.posts.filterNot { p -> p.id == post.id }) } }
    suspend fun download(file: ChatAttachment): ByteArray = withContext(Dispatchers.IO) { api.attachment(file.id).use { it.bytes() } }
    fun error(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
    private suspend fun refreshCounts() { InboxCountStore.refreshNow(); NetworkUnreadStore.refresh() }
}

object NetworkUnreadStore {
    private val mutable = MutableStateFlow(0)
    val count = mutable.asStateFlow()
    suspend fun refresh() { val generation = TokenStore.sessionGeneration(); try { val api = ApiClient.service(NetworkApi::class.java); val total = api.unread().count + api.conversations().sumOf { it.unread }; if(generation == TokenStore.sessionGeneration()) mutable.value = total } catch(e: CancellationException) { throw e } catch(_: Exception) {} }
    fun clear() { mutable.value = 0 }
}
