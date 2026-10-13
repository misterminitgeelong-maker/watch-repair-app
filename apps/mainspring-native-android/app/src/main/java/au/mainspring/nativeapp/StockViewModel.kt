package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import com.google.gson.JsonObject
import com.google.gson.JsonParser

data class StockState(
    val search: String = "", val group: String = "", val hideZero: Boolean = false,
    val items: List<StockItem> = emptyList(), val total: Int = 0,
    val sessions: List<StocktakeSession> = emptyList(), val loading: Boolean = false,
    val error: String? = null, val sessionsError: String? = null,
    val name: String = "", val createdId: String? = null, val creating: Boolean = false,
    val unknownCreate: Boolean = false, val directoryReviewed: Boolean = false,
)
class StockViewModel : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val createKey = "stocktake-create"
    private val retained = runCatching { JsonParser.parseString(drafts.loadMessageDraft(createKey)).asJsonObject }.getOrNull()
    private val mutable = MutableStateFlow(StockState(name = retained?.get("name")?.asString.orEmpty(),
        search = retained?.get("search")?.asString.orEmpty(), group = retained?.get("group")?.asString.orEmpty(),
        hideZero = retained?.get("hideZero")?.asBoolean ?: false, createdId = retained?.get("id")?.takeUnless { it.isJsonNull }?.asString,
        unknownCreate = drafts.pendingOperation(createKey)))
    val state = mutable.asStateFlow()
    private var request: Job? = null
    private var nextOffset = 0
    init { refresh() }
    fun search(value: String) { if(state.value.creating || state.value.unknownCreate) return; mutable.update { it.copy(search = value) }; load(false, true) }
    fun group(value: String) { if(state.value.creating || state.value.unknownCreate) return; mutable.update { it.copy(group = value) }; load(false, true) }
    fun hideZero(value: Boolean) { if(state.value.creating || state.value.unknownCreate) return; mutable.update { it.copy(hideZero = value) }; load(false) }
    fun name(value: String) { if(state.value.creating || state.value.unknownCreate || state.value.createdId != null) return; mutable.update { it.copy(name = value) }; persistCreate() }
    private fun persistCreate() { val s = state.value; drafts.saveMessageDraft(createKey, JsonObject().apply {
        addProperty("name", s.name); addProperty("search", s.search); addProperty("group", s.group)
        addProperty("hideZero", s.hideZero); addProperty("id", s.createdId)
    }.toString()) }
    fun another() { if(state.value.creating || state.value.unknownCreate) return; mutable.update { it.copy(name = "", createdId = null) }; persistCreate() }
    fun reviewedNotCreated() {
        if(!state.value.directoryReviewed || !state.value.unknownCreate || state.value.creating) return
        drafts.setPendingOperation(createKey, false); mutable.update { it.copy(unknownCreate = false) }
    }
    fun useExisting(id: String) {
        if(!state.value.directoryReviewed || !state.value.unknownCreate || state.value.sessions.none { it.id == id }) return
        mutable.update { it.copy(createdId = id, unknownCreate = false) }; persistCreate(); drafts.setPendingOperation(createKey, false)
    }
    fun create() {
        val s = state.value
        if(s.creating || s.unknownCreate || s.createdId != null || s.loading) return
        if(s.name.trim().isBlank() || s.name.length > 200) { mutable.update { it.copy(error = "Enter a stocktake name within 200 characters.") }; return }
        mutable.update { it.copy(creating = true, error = null) }
        viewModelScope.launch {
            var submitted = false
            try {
                persistCreate()
                check(drafts.setPendingOperation(createKey, true)) { "Could not retain the stocktake checkpoint. Check device storage and sign in again." }
                submitted = true
                val session = api.createStocktake(JsonObject().apply {
                    addProperty("name", s.name.trim()); addProperty("hide_zero_stock", s.hideZero)
                    if(s.search.isNotBlank()) addProperty("search", s.search.trim())
                    if(s.group.isNotBlank()) addProperty("group_code", s.group.trim())
                })
                mutable.update { it.copy(creating = false, createdId = session.id, sessions = listOf(session) + it.sessions.filterNot { row -> row.id == session.id }) }
                persistCreate(); drafts.setPendingOperation(createKey, false)
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val unknown = submitted && (e !is retrofit2.HttpException || e.code() >= 500)
                drafts.setPendingOperation(createKey, unknown); mutable.update { it.copy(creating = false, unknownCreate = unknown, directoryReviewed = false, error = e.userMessage()) }
            }
        }
    }
    fun refresh() { load(false); loadSessions() }
    fun more() { if(!state.value.loading && nextOffset < state.value.total) load(true) }
    private fun load(append: Boolean, debounce: Boolean = false) {
        request?.cancel()
        val selection = state.value; val offset = if(append) nextOffset else 0
        mutable.update { it.copy(loading = true, error = null, items = if(append) it.items else emptyList(), total = if(append) it.total else 0) }
        request = viewModelScope.launch {
            try {
                if(debounce) delay(300)
                val page = api.stockItems(selection.search.trim().ifBlank { null }, selection.group.trim().ifBlank { null }, selection.hideZero, offset = offset)
                nextOffset = page.offset + page.items.size
                mutable.update { it.copy(loading = false, total = page.total, items = (if(append) it.items + page.items else page.items).distinctBy { item -> item.id }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    private var sessionRequest: Job? = null
    private fun loadSessions() {
        sessionRequest?.cancel()
        mutable.update { it.copy(sessionsError = null, directoryReviewed = false) }
        sessionRequest = viewModelScope.launch {
            try { val sessions = api.stocktakes(); mutable.update { it.copy(sessions = sessions, directoryReviewed = true) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(sessionsError = e.userMessage()) } }
        }
    }
}
