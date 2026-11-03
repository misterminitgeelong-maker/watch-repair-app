package au.mainspring.nativeapp

import java.util.concurrent.CopyOnWriteArrayList
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

private data class FakeJob(val id: String, val status: String, val priority: String = "normal", val claimedBy: String? = null)

private class FakeOps(var jobs: List<FakeJob>) : QueueOps<FakeJob> {
    override val mode = "watch"
    val notes = CopyOnWriteArrayList<String>()
    val steps = CopyOnWriteArrayList<String>()
    private val seq = listOf("a", "b", "c", "d")
    override fun row(job: FakeJob) = QueueRow(job.id, job.status, job.priority, null, "2026-10-01T00:00:00Z")
    override fun nextStatus(status: String) = seq.getOrNull(seq.indexOf(status) + 1)
    override fun prevStatus(status: String) = seq.getOrNull(seq.indexOf(status) - 1)
    override fun claimedByUserId(job: FakeJob) = job.claimedBy
    override suspend fun listJobs() = jobs
    override suspend fun step(job: FakeJob, forward: Boolean): FakeJob {
        steps += "${job.id}:${if (forward) "fwd" else "back"}"
        val target = (if (forward) nextStatus(job.status) else prevStatus(job.status)) ?: error("no step")
        return job.copy(status = target).also { updated -> jobs = jobs.map { if (it.id == updated.id) updated else it } }
    }
    override suspend fun addNote(job: FakeJob, note: String) { notes += "${job.id}:$note" }
    override suspend fun setClaim(job: FakeJob, claim: Boolean) = job.copy(claimedBy = if (claim) "me" else null)
}

private class FakeStore(var day: QueueDay? = QueueDay(emptyList(), emptyList(), QueueDayStats())) : QueueDayStore {
    val saved = CopyOnWriteArrayList<QueueDay>()
    var cleared = 0
    override suspend fun load(mode: String): QueueDay = day ?: error("offline")
    override suspend fun save(mode: String, day: QueueDay) { saved += day }
    override suspend fun clear(mode: String) { cleared++ }
}

class QueueEngineTest {
    private fun engine(ops: FakeOps, store: FakeStore, online: Boolean = true) =
        QueueEngine(CoroutineScope(SupervisorJob() + Dispatchers.Unconfined), ops, store, { online }, "offline", saveDelayMs = 0)

    private fun waitFor(what: String, cond: () -> Boolean) {
        val end = System.currentTimeMillis() + 3000
        while (!cond()) { if (System.currentTimeMillis() > end) throw AssertionError("timed out: $what"); Thread.sleep(10) }
    }

    private val threeJobs get() = listOf(FakeJob("1", "a"), FakeJob("2", "b"), FakeJob("3", "c"))

    @Test fun reopeningRestoresDoneOrderAndStats() {
        val store = FakeStore(QueueDay(listOf("1"), listOf("3", "2", "1"), QueueDayStats(advanced = 1, checkedIn = 0, skipped = 2)))
        val e = engine(FakeOps(threeJobs), store)
        e.refresh()
        val s = e.state.value
        assertEquals(listOf("3", "2"), s.queue.map { it.id })
        assertEquals(1, s.doneCount); assertEquals(1, s.advanced); assertEquals(2, s.skipped)
        assertEquals(3, s.total)
        assertTrue(s.synced)
    }

    @Test fun advanceMarksDoneAndSavesToServer() {
        val store = FakeStore()
        val e = engine(FakeOps(threeJobs), store)
        e.refresh()
        e.advance()
        assertEquals(setOf("1"), e.state.value.done)
        assertEquals(1, e.state.value.advanced)
        waitFor("save") { store.saved.isNotEmpty() }
        val saved = store.saved.last()
        assertEquals(listOf("1"), saved.doneIds)
        assertEquals(1, saved.stats.advanced)
        assertEquals(3, saved.orderIds.size)
    }

    @Test fun advanceWithNoteSavesTheNoteAfterTheMove() {
        val ops = FakeOps(threeJobs)
        val e = engine(ops, FakeStore())
        e.refresh()
        e.advance("Called customer")
        assertEquals(listOf("1:fwd"), ops.steps.toList())
        assertEquals(listOf("1:Called customer"), ops.notes.toList())
    }

    @Test fun failedDayReadNeverOverwritesServerProgress() {
        val store = FakeStore(day = null)
        val e = engine(FakeOps(threeJobs), store)
        e.refresh()
        assertFalse(e.state.value.synced)
        assertEquals(3, e.state.value.queue.size)
        e.advance()
        Thread.sleep(200)
        assertTrue(store.saved.isEmpty())
    }

    @Test fun skipUndoRestoresOrder() {
        val store = FakeStore()
        val e = engine(FakeOps(threeJobs), store)
        e.refresh()
        e.skip()
        assertEquals(listOf("2", "3", "1"), e.state.value.queue.map { it.id })
        assertEquals(1, e.state.value.skipped)
        e.undo()
        assertEquals(listOf("1", "2", "3"), e.state.value.queue.map { it.id })
        assertEquals(0, e.state.value.skipped)
    }

    @Test fun noUpdateSavesNoteClearsJobAndUndoBringsItBack() {
        val ops = FakeOps(threeJobs)
        val e = engine(ops, FakeStore())
        e.refresh()
        e.noUpdate(null)
        assertEquals(listOf("1:$QUEUE_DEFAULT_CHECKED_IN_NOTE"), ops.notes.toList())
        assertEquals(1, e.state.value.checkedIn)
        assertEquals("2", e.state.value.current?.id)
        e.undo()
        assertEquals("1", e.state.value.current?.id)
        assertEquals(0, e.state.value.checkedIn)
    }

    @Test fun undoAfterAdvanceStepsTheJobBack() {
        val ops = FakeOps(threeJobs)
        val e = engine(ops, FakeStore())
        e.refresh()
        e.advance()
        e.undo()
        assertEquals(listOf("1:fwd", "1:back"), ops.steps.toList())
        assertEquals("1", e.state.value.current?.id)
        assertEquals("a", e.state.value.current?.status)
        assertEquals(0, e.state.value.advanced)
        assertTrue(e.state.value.done.isEmpty())
    }

    @Test fun filtersNarrowTheQueueWithoutLosingOrder() {
        val e = engine(FakeOps(listOf(FakeJob("1", "a", "low"), FakeJob("2", "b", "urgent"), FakeJob("3", "b", "normal"))), FakeStore())
        e.refresh()
        e.setFilters(QueueFilters(statuses = setOf("b")))
        assertEquals(listOf("2", "3"), e.state.value.queue.map { it.id })
        e.setFilters(QueueFilters(priorities = setOf("low")))
        assertEquals(listOf("1"), e.state.value.queue.map { it.id })
        e.setFilters(QueueFilters())
        assertEquals(3, e.state.value.queue.size)
    }

    @Test fun offlineBlocksServerMovesButAllowsSkip() {
        val ops = FakeOps(threeJobs)
        val e = engine(ops, FakeStore(), online = false)
        e.refresh()
        e.advance()
        assertEquals("offline", e.state.value.error)
        assertTrue(ops.steps.isEmpty())
        e.skip()
        assertEquals(1, e.state.value.skipped)
    }

    @Test fun resetDayClearsServerAndLocalProgress() {
        val store = FakeStore()
        val e = engine(FakeOps(threeJobs), store)
        e.refresh()
        e.advance()
        e.resetDay()
        assertEquals(1, store.cleared)
        assertTrue(e.state.value.done.isEmpty())
        assertEquals(0, e.state.value.advanced)
        assertEquals(3, e.state.value.queue.size)
    }

    @Test fun claimToggleReplacesTheJob() {
        val e = engine(FakeOps(threeJobs), FakeStore())
        e.refresh()
        e.toggleClaim(mine = false)
        assertEquals("me", e.state.value.current?.claimedBy)
        e.toggleClaim(mine = true)
        assertEquals(null, e.state.value.current?.claimedBy)
    }
}
