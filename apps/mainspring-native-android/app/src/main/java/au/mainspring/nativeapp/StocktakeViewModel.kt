package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class StocktakeState(
    val session: StocktakeSession? = null, val search: String = "", val hideCounted: Boolean = false,
    val lineId: String = "", val count: String = "", val notes: String = "", val originalCount: Double? = null,
    val originalNotes: String? = null, val allowNegative: Boolean = false,
    val loading: Boolean = false, val busy: Boolean = false, val uncertain: Boolean = false,
    val conflict: Boolean = false, val reviewed: Boolean = false, val error: String? = null, val info: String? = null,
    val completionUnknown: Boolean = false, val report: StocktakeReport? = null,
) {
    val editable: Boolean get() = session?.status in listOf("draft", "in_progress")
}
class StocktakeViewModel(private val id: String) : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val key = "stocktake/$id"
    private val completeKey = "stocktake-complete/$id"
    private val retained = runCatching { JsonParser.parseString(drafts.loadMessageDraft(key)).asJsonObject }.getOrNull()
    private val mutable = MutableStateFlow(StocktakeState(
        lineId = retained?.get("line")?.asString.orEmpty(), count = retained?.get("count")?.asString.orEmpty(),
        notes = retained?.get("notes")?.asString.orEmpty(),
        originalCount = retained?.get("originalCount")?.takeUnless { it.isJsonNull }?.asDouble,
        originalNotes = retained?.get("originalNotes")?.takeUnless { it.isJsonNull }?.asString,
        allowNegative = retained?.get("negative")?.asBoolean ?: false, uncertain = drafts.pendingOperation(key),
        completionUnknown = drafts.pendingOperation(completeKey),
    ))
    val state = mutable.asStateFlow()
    init { refresh() }
    fun search(value: String) { mutable.update { it.copy(search = value) } }
    fun hideCounted(value: Boolean) { mutable.update { it.copy(hideCounted = value) } }
    fun select(line: StocktakeLine) {
        if(state.value.busy || state.value.uncertain || state.value.completionUnknown || state.value.lineId.isNotBlank() || !state.value.editable) return
        mutable.update { it.copy(lineId = line.id, count = line.counted?.toString().orEmpty(), notes = line.notes.orEmpty(), originalCount = line.counted, originalNotes = line.notes, conflict = false, info = null) }; persist()
    }
    fun count(value: String) { if(state.value.busy || state.value.uncertain) return; mutable.update { it.copy(count = value) }; persist() }
    fun notes(value: String) { if(state.value.busy || state.value.uncertain) return; mutable.update { it.copy(notes = value) }; persist() }
    fun negative(value: Boolean) { if(state.value.busy || state.value.uncertain) return; mutable.update { it.copy(allowNegative = value) }; persist() }
    private fun persist() { val s = state.value; drafts.saveMessageDraft(key, JsonObject().apply {
        addProperty("line", s.lineId); addProperty("count", s.count); addProperty("notes", s.notes); addProperty("originalCount", s.originalCount)
        addProperty("originalNotes", s.originalNotes); addProperty("negative", s.allowNegative)
    }.toString()) }
    fun discard() {
        if(state.value.busy || state.value.uncertain) return
        drafts.saveMessageDraft(key, ""); mutable.update { it.copy(lineId = "", count = "", notes = "", conflict = false, error = null) }
    }
    fun refresh() {
        if(state.value.loading || state.value.busy) return
        mutable.update { it.copy(loading = true, error = null, reviewed = false) }
        viewModelScope.launch {
            try {
                val session = api.stocktake(id)
                val snapshot = state.value
                val line = session.lines.orEmpty().find { it.id == snapshot.lineId }
                val recovered = snapshot.uncertain && line != null && line.counted == snapshot.count.toDoubleOrNull() && line.notes.orEmpty() == snapshot.notes.trim()
                if(recovered) { drafts.setPendingOperation(key, false); drafts.saveMessageDraft(key, "") }
                val completed = session.status in listOf("completed", "approved")
                if(completed) drafts.setPendingOperation(completeKey, false)
                mutable.update { it.copy(session = session, loading = false, reviewed = true,
                    uncertain = if(recovered) false else it.uncertain, lineId = if(recovered) "" else it.lineId,
                    completionUnknown = if(completed) false else it.completionUnknown,
                    info = if(recovered) "Saved count found in the refreshed stocktake." else it.info) }
                if(completed) try { val report = api.stocktakeReport(id); mutable.update { it.copy(report = report) } }
                catch(e: CancellationException) { throw e }
                catch(e: Exception) { mutable.update { it.copy(error = "Stocktake loaded; summary unavailable. ${e.userMessage()}") } }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun reviewNotSaved() {
        val s = state.value
        if(!s.uncertain || !s.reviewed || s.loading || s.busy) return
        val latest = s.session?.lines.orEmpty().find { it.id == s.lineId } ?: return
        drafts.setPendingOperation(key, false)
        mutable.update { it.copy(uncertain = false, originalCount = latest.counted, originalNotes = latest.notes, conflict = false) }; persist()
    }
    fun save() {
        val s = state.value
        if(s.loading || s.busy || s.uncertain || s.completionUnknown || s.conflict || !s.editable || s.lineId.isBlank()) return
        val count = s.count.toDoubleOrNull()
        if(count == null || !count.isFinite() || kotlin.math.abs(count) > 1_000_000 || (count < 0 && !s.allowNegative)) {
            mutable.update { it.copy(error = "Enter a finite count up to 1,000,000. Confirm negative stock if needed.") }; return
        }
        mutable.update { it.copy(busy = true, error = null, info = null) }
        viewModelScope.launch {
            var submitted = false
            try {
                val fresh = api.stocktake(id)
                val latest = fresh.lines.orEmpty().find { it.id == s.lineId }
                if(fresh.status !in listOf("draft", "in_progress") || latest == null || latest.counted != s.originalCount || latest.notes != s.originalNotes) {
                    mutable.update { it.copy(busy = false, session = fresh, conflict = true, error = "This count or stocktake has changed. Discard the draft and review the latest values.") }; return@launch
                }
                persist()
                check(drafts.setPendingOperation(key, true)) { "Could not retain the count checkpoint. Check storage and sign in again." }
                submitted = true
                val saved = api.stocktakeCount(id, s.lineId, JsonObject().apply { addProperty("counted_qty", count); addProperty("notes", s.notes.trim()); addProperty("allow_negative", s.allowNegative) })
                drafts.setPendingOperation(key, false); drafts.saveMessageDraft(key, "")
                mutable.update { it.copy(busy = false, lineId = "", count = "", notes = "", session = fresh.copy(lines = fresh.lines.orEmpty().map { line -> if(line.id == saved.id) saved else line }), info = "Count saved for ${saved.code}.") }
                refresh()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val unknown = submitted && (e !is retrofit2.HttpException || e.code() >= 500)
                drafts.setPendingOperation(key, unknown)
                mutable.update { it.copy(busy = false, uncertain = unknown, reviewed = false, error = e.userMessage()) }
            }
        }
    }
    fun reviewedNotCompleted() {
        val s = state.value
        if(!s.reviewed || s.loading || s.busy || !s.editable || !s.completionUnknown) return
        drafts.setPendingOperation(completeKey, false); mutable.update { it.copy(completionUnknown = false) }
    }
    fun complete() {
        val s = state.value
        if(!TokenStore.canManageInvoices() || s.loading || s.busy || s.uncertain || s.completionUnknown || !s.editable || s.lineId.isNotBlank()) return
        val lines = s.session?.lines.orEmpty()
        if(lines.isEmpty() || lines.any { it.counted == null }) { mutable.update { it.copy(error = "Count every item before completing this stocktake.") }; return }
        mutable.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            var submitted = false
            try {
                val fresh = api.stocktake(id)
                if(fresh.status != s.session?.status || fresh.lines.orEmpty().associateBy { it.id } != lines.associateBy { it.id }) {
                    mutable.update { it.copy(busy = false, session = fresh, error = "This stocktake changed. Review the refreshed counts before completing it.") }; return@launch
                }
                check(drafts.setPendingOperation(completeKey, true)) { "Could not retain the completion checkpoint. Check storage and sign in again." }
                submitted = true
                val report = api.completeStocktake(id)
                drafts.setPendingOperation(completeKey, false)
                mutable.update { it.copy(busy = false, session = fresh.copy(status = report.session.status, completedAt = report.session.completedAt), report = report, info = "Stocktake completed; system inventory updated.") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val unknown = submitted && (e !is retrofit2.HttpException || e.code() >= 500)
                drafts.setPendingOperation(completeKey, unknown)
                mutable.update { it.copy(busy = false, completionUnknown = unknown, reviewed = false, error = e.userMessage()) }
            }
        }
    }
}
