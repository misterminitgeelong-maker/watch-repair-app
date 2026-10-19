package au.mainspring.nativeapp

import au.mainspring.nativeapp.offline.*
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

class OfflineWriteQueueTest {
    private class Mem : QueuePersistence {
        var json: String? = null
        override fun load() = json
        override fun save(json: String?) { this.json = json }
    }
    private var scope: String? = "base|t1|u1"
    private val mem = Mem()
    private var now = 1000L
    private fun queue() = OfflineWriteQueue(mem, { scope }, { now++ })
    private fun OfflineWriteQueue.add(job: String, status: String = "working_on") =
        enqueue(OfflineKinds.WATCH_STATUS, "v1/repair-jobs/$job/status", "POST", """{"status":"$status"}""", job, "Watch job: $status")

    @Test fun enqueueRecordsFieldsAndPersistsAcrossInstances() {
        val q = queue(); assertTrue(q.add("j1"))
        val item = q.state.value.pending.single()
        assertEquals("v1/repair-jobs/j1/status", item.endpoint); assertEquals("POST", item.method)
        assertEquals("j1", item.jobId); assertEquals(0, item.attempts); assertEquals("base|t1|u1", item.scope); assertTrue(item.createdAt >= 1000)
        assertEquals(item, queue().state.value.pending.single())
    }

    @Test fun refusesKindsOutsideTheSafeList() {
        assertFalse(queue().enqueue("invoice_payment", "v1/invoices/1/pay", "POST", "{}", "1", "x"))
        assertTrue(queue().state.value.pending.isEmpty())
    }

    @Test fun refusesWithoutVerifiedSession() { scope = null; assertFalse(queue().add("j1")) }

    @Test fun replaysInOrderAndEmpties() = runBlocking {
        val q = queue(); q.add("a"); q.add("b"); q.add("c")
        val sent = mutableListOf<String>()
        val r = q.replay { sent += it.jobId; 200 }
        assertEquals(ReplayResult.Done, r); assertEquals(listOf("a", "b", "c"), sent); assertTrue(q.state.value.pending.isEmpty())
    }

    @Test fun networkFailureKeepsOrderCountsAttemptAndStops() = runBlocking {
        val q = queue(); q.add("a"); q.add("b")
        val sent = mutableListOf<String>()
        assertEquals(ReplayResult.RetryLater, q.replay { sent += it.jobId; throw IOException("down") })
        assertEquals(listOf("a"), sent)
        assertEquals(listOf("a", "b"), q.state.value.pending.map { it.jobId }); assertEquals(1, q.state.value.pending[0].attempts)
        assertEquals(ReplayResult.RetryLater, q.replay { 503 }); assertEquals(2, q.state.value.pending[0].attempts)
    }

    @Test fun clientErrorMovesToNeedsAttentionAndContinues() = runBlocking {
        val q = queue(); q.add("a"); q.add("b")
        val r = q.replay { if (it.jobId == "a") 404 else 200 }
        assertEquals(ReplayResult.Done, r); assertTrue(q.state.value.pending.isEmpty())
        val att = q.state.value.attention.single(); assertEquals("a", att.item.jobId); assertEquals(404, att.code)
        q.dismissAttention(att.item.id); assertTrue(q.state.value.attention.isEmpty())
    }

    @Test fun unauthorizedStopsAndKeepsEverything() = runBlocking {
        val q = queue(); q.add("a"); q.add("b")
        assertEquals(ReplayResult.AuthStopped, q.replay { 401 })
        assertEquals(2, q.state.value.pending.size); assertTrue(q.state.value.attention.isEmpty())
    }

    @Test fun neverReplaysUnderADifferentUserOrTenant() = runBlocking {
        queue().add("a")
        scope = "base|t2|u9"
        val q = queue()
        assertTrue(q.state.value.pending.isEmpty())
        val sent = mutableListOf<String>()
        assertEquals(ReplayResult.Idle, q.replay { sent += it.jobId; 200 })
        assertTrue(sent.isEmpty())
        scope = "base|t1|u1"; assertTrue(queue().state.value.pending.isEmpty())
    }

    @Test fun scopeChangeMidReplayDoesNotSendForeignItems() = runBlocking {
        val q = queue(); q.add("a"); q.add("b")
        val sent = mutableListOf<String>()
        q.replay { sent += it.jobId; scope = "base|t2|u2"; 200 }
        assertEquals(listOf("a"), sent)
    }

    @Test fun discardAndClearAll() {
        val q = queue(); q.add("a"); q.add("b")
        q.discard(q.state.value.pending[0].id); assertEquals(listOf("b"), q.state.value.pending.map { it.jobId })
        q.clearAll(); assertTrue(q.state.value.pending.isEmpty()); assertNull(mem.json)
    }

    @Test fun backoffGrowsAndCaps() {
        assertEquals(5_000, replayBackoffMillis(1)); assertEquals(10_000, replayBackoffMillis(2))
        assertEquals(300_000, replayBackoffMillis(20)); assertEquals(5_000, replayBackoffMillis(0))
    }
}
