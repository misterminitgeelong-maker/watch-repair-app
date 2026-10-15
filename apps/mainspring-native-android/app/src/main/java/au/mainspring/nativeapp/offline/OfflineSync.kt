package au.mainspring.nativeapp.offline

import au.mainspring.nativeapp.ConnectivityMonitor
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.JobNotePayload
import au.mainspring.nativeapp.api.OfflineReplayApi
import com.google.gson.Gson
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException

/**
 * Process-wide offline write queue. Backed by the encrypted token store, so TokenStore.clear() (sign-out)
 * removes it, and each item carries the api|tenant|user scope it was made under.
 */
object OfflineSync {
    const val SAVED_OFFLINE_MESSAGE = "Saved offline, will sync"

    private val persistence = object : QueuePersistence {
        override fun load(): String? = TokenStore.loadOfflineQueue()
        override fun save(json: String?) = TokenStore.saveOfflineQueue(json)
    }
    val queue: OfflineWriteQueue by lazy { OfflineWriteQueue(persistence, { TokenStore.offlineScope() }) }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val triggers = Channel<Unit>(Channel.CONFLATED)
    private var started = false

    @Synchronized fun start() {
        if (started) return
        started = true
        scope.launch {
            for (ignored in triggers) {
                var result = replayOnce()
                while (result == ReplayResult.RetryLater) {
                    val attempts = queue.state.value.pending.firstOrNull()?.attempts ?: 1
                    delay(replayBackoffMillis(attempts))
                    result = if (ConnectivityMonitor.online.value) replayOnce() else ReplayResult.Idle
                }
            }
        }
        scope.launch { ConnectivityMonitor.online.collect { if (it) requestReplay() } }
        requestReplay()
    }

    /** Call on app start, after login/session load and whenever connectivity returns. */
    fun requestReplay() { if (started) triggers.trySend(Unit) }

    /** Sign-out: TokenStore.clear() has wiped storage; reset in-memory state. */
    fun onSessionCleared() { if (TokenStore.hasOfflineStorage()) queue.reload() }

    suspend fun replayOnce(): ReplayResult = queue.replay(sender)

    private val json = "application/json; charset=UTF-8".toMediaType()
    private val sender = WriteSender { w ->
        val api = ApiClient.service(OfflineReplayApi::class.java)
        val body = w.body.toRequestBody(json)
        val resp = when (w.method) {
            "POST" -> api.post(w.endpoint, body)
            "PUT" -> api.put(w.endpoint, body)
            "PATCH" -> api.patch(w.endpoint, body)
            else -> return@WriteSender 400
        }
        resp.body()?.close(); resp.errorBody()?.close()
        resp.code()
    }

    // ---- helpers for the view models: return true when the failure was a network failure and the write is now queued ----

    fun queueStatus(e: Throwable, kind: String, jobId: String, status: String, note: String?, customerNote: String?, label: String): Boolean {
        if (e !is IOException) return false
        val base = when (kind) {
            OfflineKinds.WATCH_STATUS -> "v1/repair-jobs"
            OfflineKinds.SHOE_STATUS -> "v1/shoe-repair-jobs"
            OfflineKinds.MOBILE_STATUS -> "v1/auto-key-jobs"
            else -> return false
        }
        val body = Gson().toJson(buildMap<String, String> {
            put("status", status); note?.let { put("note", it) }; customerNote?.let { put("customer_note", it) }
        })
        return enqueue(kind, "$base/$jobId/status", body, jobId, "$label: set status to ${status.replace('_', ' ')}")
    }

    fun queueNote(e: Throwable, kind: String, jobId: String, note: String, label: String): Boolean {
        if (e !is IOException) return false
        val base = when (kind) {
            OfflineKinds.WATCH_NOTE -> "v1/repair-jobs"
            OfflineKinds.SHOE_NOTE -> "v1/shoe-repair-jobs"
            else -> return false
        }
        return enqueue(kind, "$base/$jobId/note", Gson().toJson(JobNotePayload(note)), jobId, "$label: add note")
    }

    private fun enqueue(kind: String, endpoint: String, body: String, jobId: String, summary: String): Boolean {
        val ok = queue.enqueue(kind, endpoint, "POST", body, jobId, summary)
        if (ok) requestReplay()
        return ok
    }
}
