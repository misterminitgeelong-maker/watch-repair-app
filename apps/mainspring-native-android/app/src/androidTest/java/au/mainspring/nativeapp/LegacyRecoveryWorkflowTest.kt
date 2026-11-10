package au.mainspring.nativeapp

import android.annotation.SuppressLint
import android.os.Handler
import android.os.Looper
import android.webkit.*
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import androidx.test.platform.app.InstrumentationRegistry
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.io.ByteArrayInputStream
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.ConcurrentLinkedQueue

/** Real default WebView profile/origin migration plus tenant-verified replay; never calls a production API. */
class LegacyRecoveryWorkflowTest {
    @get:Rule val wait = HeadlessRule()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private lateinit var server: MockWebServer
    private val tenant = UUID.randomUUID().toString(); private val user = UUID.randomUUID().toString()
    private val job = UUID.randomUUID().toString(); private val otherJob = UUID.randomUUID().toString()
    private val rowId = UUID.randomUUID().toString(); private val otherRow = UUID.randomUUID().toString()
    private val requestKey = UUID.randomUUID().toString()
    private val draftKey get() = "mainspring.draft.v1.watch-intake.$tenant:$user"
    private var priorArchive: String? = null; private var priorScanned = false; private var priorHasWork = false
    @Volatile private var status = "awaiting_quote"
    private val posts = ConcurrentLinkedQueue<RecordedRequest>()
    private fun preferences() = EncryptedSharedPreferences.create(context, "mainspring_legacy_recovery", MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(), EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV, EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)
    @Before fun setup() {
        Assert.assertTrue(context.packageName.endsWith(".debug"))
        TokenStore.init(context); TokenStore.clear()
        priorArchive = preferences().getString("snapshot", null)
        val metadata = context.getSharedPreferences("mainspring_legacy_recovery_meta", android.content.Context.MODE_PRIVATE)
        priorScanned = metadata.getBoolean("scanned-v1", false); priorHasWork = metadata.getBoolean("has-work-v1", false)
        preferences().edit().remove("snapshot").commit(); metadata.edit().clear().commit()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                if(request.method == "POST") { posts.add(request); status = "completed" }
                val id = if(path.contains(otherJob)) otherJob else job
                val responseTenant = if(id == otherJob) UUID.randomUUID().toString() else tenant
                return MockResponse().setHeader("Content-Type", "application/json").setBody("""{"id":"$id","tenant_id":"$responseTenant","job_number":"W001","title":"Previous app repair","status":"$status","updated_at":"2026-11-11T00:00:00Z"}""")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.saveTokens("synthetic-native-token", null); TokenStore.setDraftScope(tenant, user); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() {
        runCatching { executeOrigin("""localStorage.removeItem(${Gson().toJson(draftKey)});const db=await openDatabase();if(db){await new Promise((resolve,reject)=>{const tx=db.transaction('queue','readwrite');tx.objectStore('queue').delete('$rowId');tx.objectStore('queue').delete('$otherRow');tx.oncomplete=resolve;tx.onerror=reject;});db.close();}return true;""") }
        val edit = preferences().edit()
        if(priorArchive == null) edit.remove("snapshot") else edit.putString("snapshot", priorArchive)
        edit.commit()
        context.getSharedPreferences("mainspring_legacy_recovery_meta", android.content.Context.MODE_PRIVATE).edit().putBoolean("scanned-v1", priorScanned).putBoolean("has-work-v1", priorHasWork).commit()
        TokenStore.clear(); server.shutdown()
    }
    @SuppressLint("SetJavaScriptEnabled") private fun executeOrigin(script: String): String {
        val latch = CountDownLatch(1); var result = ""; var failure: String? = null; var web: WebView? = null
        val html = """<script>async function openDatabase(){return await new Promise((resolve,reject)=>{const r=indexedDB.open('mainspring-offline',2);r.onupgradeneeded=()=>{for(const s of ['queue','dead'])if(!r.result.objectStoreNames.contains(s))r.result.createObjectStore(s,{keyPath:'id'});};r.onsuccess=()=>resolve(r.result);r.onerror=reject;});}(async()=>{$script})().then(value=>Fixture.done(JSON.stringify(value))).catch(e=>Fixture.failed(String(e)));</script>"""
        InstrumentationRegistry.getInstrumentation().runOnMainSync {
            web = WebView(context).apply {
                settings.javaScriptEnabled = true; settings.domStorageEnabled = true
                addJavascriptInterface(object {
                    @JavascriptInterface fun done(value: String) { result = value; latch.countDown() }
                    @JavascriptInterface fun failed(value: String) { failure = value; latch.countDown() }
                }, "Fixture")
                webViewClient = object: WebViewClient() { override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?) = WebResourceResponse("text/html", "UTF-8", ByteArrayInputStream(if(request?.url?.toString() == "https://localhost/__legacy_test_fixture__") html.toByteArray() else byteArrayOf())) }
                loadUrl("https://localhost/__legacy_test_fixture__")
            }
        }
        Assert.assertTrue("Local-origin WebView fixture timed out", latch.await(20, TimeUnit.SECONDS))
        InstrumentationRegistry.getInstrumentation().runOnMainSync { web?.destroy() }
        Assert.assertNull(failure); return result
    }
    private fun seedAndScan() {
        val envelope = Gson().toJson(mapOf("v" to 1, "kind" to "watch-intake", "scope" to "$tenant:$user", "savedAt" to 1, "data" to mapOf("job" to mapOf("title" to "Old unfinished service"))))
        val rows = Gson().toJson(listOf(rowId to job, otherRow to otherJob).map { (id, target) -> mapOf("id" to id, "url" to "https://mainspring.au/v1/repair-jobs/$target/status", "method" to "post", "body" to """{"status":"completed"}""", "userId" to user, "idempotencyKey" to requestKey, "createdAt" to "2026-11-10T10:00:00Z", "expectedUpdatedAt" to "2026-11-11T00:00:00Z") })
        executeOrigin("""localStorage.setItem(${Gson().toJson(draftKey)},${Gson().toJson(envelope)});const db=await openDatabase();await new Promise((resolve,reject)=>{const tx=db.transaction('queue','readwrite');for(const row of $rows)tx.objectStore('queue').put(row);tx.oncomplete=resolve;tx.onerror=reject;});db.close();return true;""")
        val done = CountDownLatch(1); var failure: Throwable? = null
        scanLegacyWork(context) { failure = it.exceptionOrNull(); done.countDown() }
        Assert.assertTrue(done.await(20, TimeUnit.SECONDS)); Assert.assertNull(failure)
    }
    @Test fun readerPreservesExpiredDraftAndOriginalIndexedDbWithoutDeletingEither() {
        seedAndScan()
        val snapshot = LegacyRecoveryStore.snapshot(context)!!
        Assert.assertEquals("Old unfinished service", legacyDrafts(snapshot, tenant, user).single().data!!.getAsJsonObject("job")["title"].asString)
        val original = executeOrigin("""const db=await openDatabase();const rows=await new Promise((resolve,reject)=>{const r=db.transaction('queue','readonly').objectStore('queue').getAll();r.onsuccess=()=>resolve(r.result);r.onerror=reject;});db.close();return {draft:localStorage.getItem(${Gson().toJson(draftKey)}),exists:rows.some(r=>r.id==='$rowId')};""")
        val json = JsonParser.parseString(original).asJsonObject
        Assert.assertTrue(json["exists"].asBoolean); Assert.assertFalse(json["draft"].isJsonNull)
    }
    @Test fun onlyVerifiedTenantRowsAreExposedAndExportsNeverResubmitOldRequests() {
        seedAndScan(); val model = LegacyRecoveryViewModel(context.applicationContext as android.app.Application)
        wait.waitUntil(15_000) { !model.state.value.loading }
        Assert.assertEquals(1, model.state.value.drafts.size); Assert.assertEquals(listOf(rowId), model.state.value.writes.map { it.id }); Assert.assertEquals(1, model.state.value.unmatched)
        val write = model.state.value.writes.single()
        val exported = JsonParser.parseString(model.exportWrite(write)).asJsonObject
        Assert.assertEquals(requestKey, exported["idempotencyKey"].asString)
        Assert.assertEquals("2026-11-11T00:00:00Z", exported["expectedUpdatedAt"].asString)
        Assert.assertEquals("completed", JsonParser.parseString(exported["body"].asString).asJsonObject["status"].asString)
        Assert.assertTrue(posts.isEmpty())
        val draft = JsonParser.parseString(model.exportDraft(model.state.value.drafts.single())).asJsonObject
        Assert.assertEquals("Old unfinished service", draft.getAsJsonObject("data").getAsJsonObject("job")["title"].asString)
    }
    @Test fun changedSignInCannotExportPreviouslyViewedData() {
        seedAndScan(); val model = LegacyRecoveryViewModel(context.applicationContext as android.app.Application)
        wait.waitUntil(15_000) { !model.state.value.loading }
        val draft = model.state.value.drafts.single(); val write = model.state.value.writes.single()
        TokenStore.saveTokens("another-synthetic-token", null); TokenStore.setDraftScope(UUID.randomUUID().toString(), UUID.randomUUID().toString())
        Assert.assertFalse(model.canExport())
        Assert.assertThrows(IllegalStateException::class.java) { model.exportDraft(draft) }
        Assert.assertThrows(IllegalStateException::class.java) { model.exportWrite(write) }
        Assert.assertTrue(posts.isEmpty())
    }

}
