package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.OfflineReplayApi
import au.mainspring.nativeapp.offline.*
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Retrofit

class OfflineReplaySafetyTest {
    private class Mem : QueuePersistence {
        var json: String? = null
        override fun load() = json
        override fun save(json: String?) { this.json = json }
    }
    private val mem = Mem()
    private var now = 1000L
    private fun queue() = OfflineWriteQueue(mem, { "s" }, { now++ })
    private val server = MockWebServer()
    @After fun stop() { try { server.shutdown() } catch (_: Exception) {} }
    private fun sender(): HttpWriteSender {
        server.start()
        val api = Retrofit.Builder().baseUrl(server.url("/")).build().create(OfflineReplayApi::class.java)
        return HttpWriteSender { api }
    }
    private fun OfflineWriteQueue.watchStatus(job: String, base: String, target: String) =
        enqueue(OfflineKinds.WATCH_STATUS, "v1/repair-jobs/$job/status", "POST", """{"status":"$target"}""", job, "Watch job: $target", baseStatus = base, targetStatus = target)

    @Test fun noteRetryAfterTimeoutReusesTheSameIdempotencyKey() = runBlocking {
        val q = queue()
        q.enqueue(OfflineKinds.WATCH_NOTE, "v1/repair-jobs/j/note", "POST", """{"note":"hi"}""", "j", "note")
        q.enqueue(OfflineKinds.WATCH_NOTE, "v1/repair-jobs/j/note", "POST", """{"note":"yo"}""", "j", "note")
        val (a, b) = q.state.value.pending
        assertNotNull(a.idempotencyKey); assertNotEquals(a.idempotencyKey, b.idempotencyKey)
        val s = sender()
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST))
        server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        assertEquals(ReplayResult.RetryLater, q.replay(s))
        assertEquals(ReplayResult.Done, q.replay(s))
        val first = server.takeRequest(); val retry = server.takeRequest()
        assertEquals(a.idempotencyKey, first.getHeader("Idempotency-Key")); assertEquals(first.getHeader("Idempotency-Key"), retry.getHeader("Idempotency-Key"))
        assertEquals(b.idempotencyKey, server.takeRequest().getHeader("Idempotency-Key"))
    }

    @Test fun inProgressDuplicateIsRetriedNotTreatedAsConflict() = runBlocking {
        val q = queue(); q.enqueue(OfflineKinds.SHOE_NOTE, "v1/shoe-repair-jobs/j/note", "POST", "{}", "j", "note")
        val s = sender()
        server.enqueue(MockResponse().setResponseCode(409).setBody("""{"detail":"idempotent_request_in_progress"}"""))
        assertEquals(ReplayResult.RetryLater, q.replay(s))
        assertEquals(1, q.state.value.pending.size); assertTrue(q.state.value.attention.isEmpty())
    }

    @Test fun mobileStatusSendsExpectedUpdatedAtAndStaleGoesToAttention() = runBlocking {
        val q = queue()
        q.enqueue(OfflineKinds.MOBILE_STATUS, "v1/auto-key-jobs/m/status", "POST", """{"status":"done"}""", "m", "Mobile job: done",
            expectedUpdatedAt = "2026-10-01T10:00:00Z", targetStatus = "done")
        val s = sender()
        server.enqueue(MockResponse().setResponseCode(409).setBody("""{"detail":"stale_write"}"""))
        q.replay(s)
        assertEquals("2026-10-01T10:00:00Z", server.takeRequest().getHeader("X-Expected-Updated-At"))
        val att = q.state.value.attention.single(); assertTrue(att.canApplyAnyway); assertTrue(att.reason.contains("someone else"))
        assertTrue(q.state.value.pending.isEmpty())
    }

    @Test fun applyAnywayRequeuesWithoutPreconditionsAndWithFreshKey() = runBlocking {
        val q = queue()
        q.enqueue(OfflineKinds.MOBILE_STATUS, "v1/auto-key-jobs/m/status", "POST", """{"status":"done"}""", "m", "x",
            expectedUpdatedAt = "2026-10-01T10:00:00Z", targetStatus = "done")
        val oldKey = q.state.value.pending.single().idempotencyKey
        val s = sender()
        server.enqueue(MockResponse().setResponseCode(409).setBody("""{"detail":"stale_write"}"""))
        q.replay(s); server.takeRequest()
        val id = q.state.value.attention.single().item.id
        assertTrue(q.applyAnyway(id))
        assertTrue(q.state.value.attention.isEmpty())
        val redo = q.state.value.pending.single(); assertTrue(redo.force); assertNull(redo.expectedUpdatedAt); assertNotEquals(oldKey, redo.idempotencyKey)
        server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        assertEquals(ReplayResult.Done, q.replay(s))
        val req = server.takeRequest(); assertNull(req.getHeader("X-Expected-Updated-At")); assertEquals(redo.idempotencyKey, req.getHeader("Idempotency-Key"))
    }

    @Test fun watchStatusSentOnlyWhileLiveStatusIsWhatUserSaw() = runBlocking {
        val q = queue(); q.watchStatus("w", "received", "working_on")
        val s = sender()
        server.enqueue(MockResponse().setResponseCode(200).setBody("""{"status":"received"}"""))
        server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        assertEquals(ReplayResult.Done, q.replay(s))
        assertEquals("GET", server.takeRequest().method); assertEquals("POST", server.takeRequest().method)
    }

    @Test fun watchStatusChangedOnServerIsNotOverwrittenAndNothingIsPosted() = runBlocking {
        val q = queue(); q.watchStatus("w", "received", "working_on")
        val s = sender()
        server.enqueue(MockResponse().setResponseCode(200).setBody("""{"status":"ready"}"""))
        q.replay(s)
        assertEquals(1, server.requestCount)
        val att = q.state.value.attention.single(); assertEquals(412, att.code); assertTrue(att.canApplyAnyway)
        q.applyAnyway(att.item.id)
        server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        assertEquals(ReplayResult.Done, q.replay(s))
        assertEquals("GET", server.takeRequest().method); assertEquals("POST", server.takeRequest().method)
        assertEquals(2, server.requestCount)
    }

    @Test fun alreadyAppliedStatusIsDroppedAsSyncedWithoutPosting() = runBlocking {
        val q = queue(); q.watchStatus("w", "received", "working_on")
        val s = sender()
        server.enqueue(MockResponse().setResponseCode(200).setBody("""{"status":"working_on"}"""))
        assertEquals(ReplayResult.Done, q.replay(s))
        assertEquals(1, server.requestCount); assertTrue(q.state.value.pending.isEmpty() && q.state.value.attention.isEmpty())
    }

    @Test fun chainedStatusChangesExpectTheEarlierOnesResult() {
        val q = queue(); q.watchStatus("w", "received", "working_on"); q.watchStatus("w", "received", "ready")
        val (first, second) = q.state.value.pending
        assertEquals("received", first.baseStatus); assertEquals("working_on", second.baseStatus)
        assertEquals("ready", q.state.value.pendingStatusFor("w")); assertNull(q.state.value.pendingStatusFor("other"))
        val m = q
        m.enqueue(OfflineKinds.MOBILE_STATUS, "v1/auto-key-jobs/m/status", "POST", "{}", "m", "a", expectedUpdatedAt = "t1", targetStatus = "x")
        m.enqueue(OfflineKinds.MOBILE_STATUS, "v1/auto-key-jobs/m/status", "POST", "{}", "m", "b", expectedUpdatedAt = "t1", targetStatus = "y")
        assertEquals(listOf<String?>("t1", null), m.state.value.pending.filter { it.jobId == "m" }.map { it.expectedUpdatedAt })
    }

    @Test fun legacyPersistedItemsWithoutNewFieldsStillReplay() = runBlocking {
        mem.json = """{"pending":[{"id":"old","scope":"s","kind":"watch_note","endpoint":"v1/repair-jobs/j/note","method":"POST","body":"{}","jobId":"j","summary":"n","createdAt":1,"attempts":0}],"attention":[]}"""
        val q = queue(); val item = q.state.value.pending.single()
        assertEquals("old", item.effectiveIdempotencyKey()); assertFalse(item.force)
        val s = sender(); server.enqueue(MockResponse().setResponseCode(200).setBody("{}"))
        assertEquals(ReplayResult.Done, q.replay(s)); assertEquals("old", server.takeRequest().getHeader("Idempotency-Key"))
    }
}
