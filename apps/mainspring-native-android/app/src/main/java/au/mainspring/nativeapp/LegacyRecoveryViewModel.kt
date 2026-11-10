package au.mainspring.nativeapp

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.GsonBuilder
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class RecoveredWrite(val id: String, val row: JsonObject, val target: LegacyWriteTarget, val title: String,
    val liveStatus: String?, val updatedAt: String?, val dead: Boolean)
data class LegacyRecoveryState(val loading: Boolean = false, val busy: Boolean = false, val error: String? = null, val info: String? = null,
    val drafts: List<LegacyDraft> = emptyList(), val writes: List<RecoveredWrite> = emptyList(), val unmatched: Int = 0,
    val scanned: Boolean = false)

class LegacyRecoveryViewModel(app: Application): AndroidViewModel(app) {
    private val api = ApiClient.service(OfflineReplayApi::class.java)
    private val tenant = TokenStore.currentTenantId()
    private val user = TokenStore.currentUserId()
    private val generation = TokenStore.sessionGeneration()
    private val mutable = MutableStateFlow(LegacyRecoveryState())
    val state = mutable.asStateFlow()
    init { if(LegacyRecoveryStore.scanned(app)) refresh() else scan() }
    private fun sessionCurrent() = generation == TokenStore.sessionGeneration() && tenant == TokenStore.currentTenantId() && user == TokenStore.currentUserId() && TokenStore.getAccessToken() != null
    fun scan() {
        if(mutable.value.loading || mutable.value.busy) return
        mutable.update { it.copy(loading = true, error = null) }
        scanLegacyWork(getApplication()) { result ->
            if(!sessionCurrent()) { mutable.value = LegacyRecoveryState(error = "Your sign-in changed. Reopen recovery in the current shop."); return@scanLegacyWork }
            mutable.update { it.copy(loading = false, error = result.exceptionOrNull()?.let { e -> if(e is Exception) e.userMessage() else e.message ?: "Could not recover previous app work." }) }
            if(result.isSuccess) refresh()
        }
    }
    private suspend fun live(target: LegacyWriteTarget): JsonObject {
        check(sessionCurrent()) { "Your sign-in changed. Reopen recovery in the current shop." }
        val response = api.get(target.readPath)
        val body = try { response.body()?.string() } finally { response.errorBody()?.close() }
        if(!response.isSuccessful) throw retrofit2.HttpException(response)
        val job = JsonParser.parseString(body).asJsonObject
        check(job.legacyString("tenant_id") == tenant && job.legacyString("id") == target.jobId && sessionCurrent()) { "This saved change could not be matched to the current shop." }
        return job
    }
    fun refresh() {
        if(mutable.value.loading || mutable.value.busy || !sessionCurrent()) return
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val archive = withContext(Dispatchers.IO) { LegacyRecoveryStore.snapshot(getApplication()) }
                if(archive == null) { mutable.update { it.copy(loading = false, scanned = true) }; return@launch }
                val drafts = legacyDrafts(archive, tenant, user)
                val dead = archive.legacyObjects("dead")
                val deadIds = dead.mapNotNull { it.legacyString("id") }.toSet()
                val ownRows = (dead + archive.legacyObjects("queue")).filter { it.legacyString("userId") == user }.distinctBy { it.legacyString("id") }
                val matched = mutableListOf<RecoveredWrite>()
                for(row in ownRows) {
                    val target = legacyWriteTarget(row) ?: continue
                    try {
                        val job = live(target)
                        val id = row.legacyString("id")!!
                        matched.add(RecoveredWrite(id, row, target, listOfNotNull(job.legacyString("job_number"), job.legacyString("title")).joinToString(" · "), job.legacyString("status"), job.legacyString("updated_at"), id in deadIds))
                    } catch(e: CancellationException) { throw e } catch(e: Exception) {
                        // A row has no tenant field. Never expose its body unless the target is verified in this shop.
                        if(e !is retrofit2.HttpException || e.code() !in listOf(403, 404)) mutable.update { it.copy(error = "Some saved changes could not be checked. They remain preserved. ${e.userMessage()}") }
                    }
                }
                check(sessionCurrent()) { "Your sign-in changed. Reopen recovery in the current shop." }
                mutable.update { it.copy(loading = false, scanned = true, drafts = drafts, writes = matched, unmatched = ownRows.size - matched.size) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    /** Recovery never resubmits an old write: its original result may have been lost and cannot be safely inferred. */
    fun canExport(): Boolean = sessionCurrent()
    fun exportDraft(draft: LegacyDraft): String { check(sessionCurrent() && mutable.value.drafts.any { it.key == draft.key && it.envelope == draft.envelope }); return GsonBuilder().setPrettyPrinting().create().toJson(draft.envelope) }
    fun exportWrite(write: RecoveredWrite): String { check(sessionCurrent() && mutable.value.writes.any { it.id == write.id }); return GsonBuilder().setPrettyPrinting().create().toJson(write.row) }
    fun error(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
}
