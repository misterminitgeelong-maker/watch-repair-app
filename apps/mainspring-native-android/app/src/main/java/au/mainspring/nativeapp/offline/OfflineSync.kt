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

    /** "Apply anyway" on a stale-refused status change. */
    fun applyAnyway(id: String) { if (queue.applyAnyway(id)) requestReplay() }

    /** Sign-out: TokenStore.clear() has wiped storage; reset in-memory state. */
    fun onSessionCleared() { if (TokenStore.hasOfflineStorage()) queue.reload() }

    suspend fun replayOnce(): ReplayResult = queue.replay(sender)

    private val sender = HttpWriteSender { ApiClient.service(OfflineReplayApi::class.java) }

    // ---- helpers for the view models: return true when the failure was a network failure and the write is now queued ----

    fun queueStatus(
        e: Throwable, kind: String, jobId: String, status: String, note: String?, customerNote: String?, label: String,
        /** Mobile jobs: the `updated_at` the user saw. Watch/shoe jobs: pass [baseStatus] (the status the user saw) instead. */
        expectedUpdatedAt: String? = null, baseStatus: String? = null,
    ): Boolean {
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
        return enqueue(kind, "$base/$jobId/status", body, jobId, "$label: set status to ${status.replace('_', ' ')}", expectedUpdatedAt, baseStatus, status)
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

    /** Queue an edit of a mobile job's technician notes. The server refuses it (409) if the job changed since [expectedUpdatedAt], and it then needs review. */
    fun queueMobileNote(e: Throwable, jobId: String, notes: String, label: String, expectedUpdatedAt: String?): Boolean {
        if (e !is IOException) return false
        val body = Gson().toJson(mapOf("tech_notes" to notes))
        val ok = queue.enqueue(OfflineKinds.MOBILE_NOTE, "v1/auto-key-jobs/$jobId", "PATCH", body, jobId, "$label: update technician notes", expectedUpdatedAt)
        if (ok) requestReplay()
        return ok
    }

    private fun enqueue(kind: String, endpoint: String, body: String, jobId: String, summary: String,
                        expectedUpdatedAt: String? = null, baseStatus: String? = null, targetStatus: String? = null): Boolean {
        val ok = queue.enqueue(kind, endpoint, "POST", body, jobId, summary, expectedUpdatedAt, baseStatus, targetStatus)
        if (ok) requestReplay()
        return ok
    }
}
