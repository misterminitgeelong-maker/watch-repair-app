package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.offline.OfflineKinds
import au.mainspring.nativeapp.offline.OfflineSync
import au.mainspring.nativeapp.offline.ReplayResult
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.*
import java.io.IOException

/** A note made while the server is unreachable is queued, then replayed to the same endpoint once it is back. */
class OfflineQueueReplayTest {
    private lateinit var server: MockWebServer
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant-q", "user-q")
        TokenStore.saveTokens("access", "refresh"); OfflineSync.queue.reload()
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun queuedNoteReplaysAndLogoutClearsQueue() = runBlocking {
        Assert.assertTrue(OfflineSync.queueNote(IOException("down"), OfflineKinds.WATCH_NOTE, "job-1", "Called customer", "Watch job"))
        Assert.assertEquals(1, OfflineSync.queue.state.value.pending.size)
        server.enqueue(MockResponse().setResponseCode(204))
        Assert.assertEquals(ReplayResult.Done, OfflineSync.replayOnce())
        val req = server.takeRequest()
        Assert.assertEquals("/v1/repair-jobs/job-1/note", req.path); Assert.assertTrue(req.body.readUtf8().contains("Called customer"))
        Assert.assertTrue(OfflineSync.queue.state.value.pending.isEmpty())
        OfflineSync.queueStatus(IOException("down"), OfflineKinds.SHOE_STATUS, "s1", "ready", null, null, "Shoe job")
        TokenStore.clear()
        Assert.assertTrue(OfflineSync.queue.state.value.pending.isEmpty())
    }
}
