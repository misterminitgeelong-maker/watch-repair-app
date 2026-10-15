package au.mainspring.nativeapp.offline

import com.google.gson.Gson
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.IOException
import java.util.UUID

/** One idempotent, low-risk write captured while offline. Never payments, invoices, deletes or creates. */
data class QueuedWrite(
    val id: String,
    /** Session scope (api base | tenant | user) the write was made under; it only ever replays under the same scope. */
    val scope: String,
    val kind: String,
    val endpoint: String,
    val method: String,
    val body: String,
    val jobId: String,
    val summary: String,
    val createdAt: Long,
    val attempts: Int = 0,
    /** Sent as `Idempotency-Key` so a retry after a timeout the server did receive cannot apply twice. Null on items queued by older builds (falls back to [id]). */
    val idempotencyKey: String? = null,
    /** Mobile jobs: the `updated_at` the user saw. Sent as `X-Expected-Updated-At` on replay. */
    val expectedUpdatedAt: String? = null,
    /** Watch/shoe jobs (no server-side stale header): the status the user saw, compared with the live job before replay. */
    val baseStatus: String? = null,
    val targetStatus: String? = null,
    /** True after "Apply anyway": skip every stale check. */
    val force: Boolean = false,
) {
    val isStatus: Boolean get() = kind == OfflineKinds.WATCH_STATUS || kind == OfflineKinds.SHOE_STATUS || kind == OfflineKinds.MOBILE_STATUS
    fun effectiveIdempotencyKey(): String = idempotencyKey ?: id
}

data class NeedsAttention(val item: QueuedWrite, val reason: String, val code: Int?, val at: Long) {
    /** A status change the server refused because the job moved on; the user may choose to apply it anyway. */
    val canApplyAnyway: Boolean get() = item.isStatus && (code == 409 || code == 412)
}

/** The status a job is waiting to be moved to by a queued (not yet synced) change, if any. */
fun QueueSnapshot.pendingStatusFor(jobId: String): String? =
    pending.lastOrNull { it.jobId == jobId && it.isStatus && it.targetStatus != null }?.targetStatus

data class QueueSnapshot(val pending: List<QueuedWrite> = emptyList(), val attention: List<NeedsAttention> = emptyList())

interface QueuePersistence {
    fun load(): String?
    fun save(json: String?)
}

/** Sends one write and returns the HTTP status code. Network failure must throw [IOException]. */
fun interface WriteSender { suspend fun send(write: QueuedWrite): Int }

enum class ReplayResult { Idle, Done, RetryLater, AuthStopped }

object OfflineKinds {
    const val WATCH_STATUS = "watch_status"
    const val SHOE_STATUS = "shoe_status"
    const val MOBILE_STATUS = "mobile_status"
    const val WATCH_NOTE = "watch_note"
    const val SHOE_NOTE = "shoe_note"
    val ALLOWED = setOf(WATCH_STATUS, SHOE_STATUS, MOBILE_STATUS, WATCH_NOTE, SHOE_NOTE)
}

/** 5s, 10s, 20s ... capped at 5 minutes. */
fun replayBackoffMillis(attempts: Int): Long = (5_000L shl (attempts.coerceIn(1, 7) - 1)).coerceAtMost(300_000L)

class OfflineWriteQueue(
    private val persistence: QueuePersistence,
    private val scopeProvider: () -> String?,
    private val clock: () -> Long = System::currentTimeMillis,
    private val maxPending: Int = 200,
    private val maxAttention: Int = 50,
) {
    private val gson = Gson()
    private val lock = Any()
    private val replayLock = Mutex()
    private var all = QueueSnapshot()
    private val visible = MutableStateFlow(QueueSnapshot())
    /** Items for the signed-in scope only. */
    val state: StateFlow<QueueSnapshot> = visible.asStateFlow()

    init { reload() }

    /** Re-read storage and drop anything that does not belong to the current session scope. */
    fun reload() = synchronized(lock) {
        all = try { persistence.load()?.let { gson.fromJson(it, QueueSnapshot::class.java) } ?: QueueSnapshot() } catch (_: Exception) { QueueSnapshot() }
        val scope = scopeProvider()
        // A queue must never survive into another user/tenant: purge foreign items outright.
        val kept = QueueSnapshot(all.pending.filter { it.scope == scope }, all.attention.filter { it.item.scope == scope })
        val changed = kept.pending.size != all.pending.size || kept.attention.size != all.attention.size
        all = kept
        if (changed) persistence.save(gson.toJson(all))
        publish()
    }

    fun clearAll() = synchronized(lock) { all = QueueSnapshot(); persistence.save(null); visible.value = all }

    fun enqueue(
        kind: String, endpoint: String, method: String, body: String, jobId: String, summary: String,
        expectedUpdatedAt: String? = null, baseStatus: String? = null, targetStatus: String? = null,
    ): Boolean = synchronized(lock) {
        val scope = scopeProvider() ?: return false
        if (kind !in OfflineKinds.ALLOWED || all.pending.size >= maxPending) return false
        // A second change to the same job builds on the first: it expects the first's result, not what the user saw originally,
        // and the first one's replay will have moved updated_at, so the timestamp precondition no longer applies.
        val earlier = all.pending.lastOrNull { it.jobId == jobId && it.kind == kind && it.targetStatus != null }
        val base = if (earlier != null) earlier.targetStatus else baseStatus
        val expected = if (earlier != null) null else expectedUpdatedAt
        val id = UUID.randomUUID().toString()
        val item = QueuedWrite(id, scope, kind, endpoint, method.uppercase(), body, jobId, summary, clock(),
            idempotencyKey = UUID.randomUUID().toString(), expectedUpdatedAt = expected, baseStatus = base, targetStatus = targetStatus)
        all = all.copy(pending = all.pending + item); persist(); true
    }

    /**
     * "Apply anyway": put a refused status change back on the queue with no stale checks and a fresh idempotency key
     * (the server cached the refusal under the old key). Returns false if the item is not in Needs attention.
     */
    fun applyAnyway(id: String): Boolean = synchronized(lock) {
        val a = all.attention.firstOrNull { it.item.id == id && it.canApplyAnyway } ?: return false
        if (all.pending.size >= maxPending) return false
        val redo = a.item.copy(attempts = 0, force = true, expectedUpdatedAt = null, baseStatus = null, idempotencyKey = UUID.randomUUID().toString())
        all = all.copy(attention = all.attention.filterNot { it.item.id == id }, pending = all.pending + redo); persist(); true
    }

    fun discard(id: String) = synchronized(lock) { all = all.copy(pending = all.pending.filterNot { it.id == id }); persist() }
    fun dismissAttention(id: String) = synchronized(lock) { all = all.copy(attention = all.attention.filterNot { it.item.id == id }); persist() }
    fun dismissAllAttention() = synchronized(lock) { all = all.copy(attention = emptyList()); persist() }

    private fun persist() { persistence.save(gson.toJson(all)); publish() }
    private fun publish() {
        val scope = scopeProvider()
        visible.value = QueueSnapshot(all.pending.filter { it.scope == scope }, all.attention.filter { it.item.scope == scope })
    }

    /** Replays in order. Stops at the first transient failure or a 401 so ordering is preserved. */
    suspend fun replay(sender: WriteSender): ReplayResult = replayLock.withLock {
        var sent = 0
        while (true) {
            val scope = scopeProvider()
            val next = synchronized(lock) {
                if (scope == null) null else {
                    // Foreign-scope items are removed, never sent.
                    if (all.pending.any { it.scope != scope }) { all = all.copy(pending = all.pending.filter { it.scope == scope }); persist() }
                    all.pending.firstOrNull()
                }
            } ?: return@withLock if (sent > 0) ReplayResult.Done else ReplayResult.Idle
            val code = try { sender.send(next) } catch (_: IOException) {
                markAttempt(next.id); return@withLock ReplayResult.RetryLater
            }
            when {
                code in 200..299 -> { remove(next.id); sent++ }
                code == 401 -> return@withLock ReplayResult.AuthStopped
                code == 408 || code == 429 || code >= 500 -> { markAttempt(next.id); return@withLock ReplayResult.RetryLater }
                else -> synchronized(lock) {
                    all = all.copy(
                        pending = all.pending.filterNot { it.id == next.id },
                        attention = (listOf(NeedsAttention(next, reasonFor(next, code), code, clock())) + all.attention).take(maxAttention),
                    ); persist()
                }
            }
        }
        @Suppress("UNREACHABLE_CODE") ReplayResult.Idle
    }

    private fun remove(id: String) = synchronized(lock) { all = all.copy(pending = all.pending.filterNot { it.id == id }); persist() }
    private fun markAttempt(id: String) = synchronized(lock) {
        all = all.copy(pending = all.pending.map { if (it.id == id) it.copy(attempts = it.attempts + 1) else it }); persist()
    }
    private fun reasonFor(w: QueuedWrite, code: Int) = when (code) {
        403 -> "Your account cannot make this change."
        404 -> "This job no longer exists."
        409, 412 -> if (!w.isStatus) "The job changed on the server; review it and redo this change." else "This job was changed by someone else after you made this change. Applying it now would overwrite their update."
        else -> "The server rejected this change ($code)."
    }
}
