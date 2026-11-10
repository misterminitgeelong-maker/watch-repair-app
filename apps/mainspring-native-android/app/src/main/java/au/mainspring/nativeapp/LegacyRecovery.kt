package au.mainspring.nativeapp

import android.annotation.SuppressLint
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.io.ByteArrayInputStream
import java.net.URI
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

internal fun JsonObject.legacyString(key: String): String? = get(key)?.takeIf { it.isJsonPrimitive }?.runCatching { asString }?.getOrNull()
internal fun JsonObject.legacyObjects(key: String): List<JsonObject> = get(key)?.takeIf { it.isJsonArray }?.asJsonArray?.filter { it.isJsonObject }?.map { it.asJsonObject }.orEmpty()

data class LegacyDraft(val key: String, val envelope: JsonObject) {
    val kind get() = envelope.legacyString("kind").orEmpty()
    val data: JsonObject? get() = envelope.get("data")?.takeIf { it.isJsonObject }?.asJsonObject
}

/** Only the exact signed-in shop/user scope is readable; expired drafts remain recoverable without running the old TTL sweep. */
fun legacyDrafts(snapshot: JsonObject, tenant: String, user: String): List<LegacyDraft> = snapshot.legacyObjects("drafts").mapNotNull { entry ->
    val key = entry.legacyString("key") ?: return@mapNotNull null
    val raw = entry.legacyString("value") ?: return@mapNotNull null
    val envelope = runCatching { JsonParser.parseString(raw).asJsonObject }.getOrNull() ?: return@mapNotNull null
    if(tenant.isBlank() || user.isBlank() || envelope.legacyString("scope") != "$tenant:$user") null else LegacyDraft(key, envelope)
}

data class LegacyWriteTarget(val readPath: String, val writePath: String, val method: String, val body: JsonObject, val jobId: String)

/** The old queue lacks a tenant id. Only known existing-job writes can be matched by a live, tenant-scoped read. */
fun legacyWriteTarget(row: JsonObject): LegacyWriteTarget? { return runCatching {
    val raw = row.legacyString("url") ?: return null
    val uri = URI(raw)
    if(uri.rawQuery != null || uri.rawFragment != null || uri.userInfo != null) return null
    if(uri.isAbsolute && (uri.scheme != "https" || uri.host !in setOf("mainspring.au", "www.mainspring.au") || uri.port !in setOf(-1, 443))) return null
    if(!uri.isAbsolute && uri.rawAuthority != null) return null
    val path = uri.path.trimStart('/')
    val match = Regex("^v1/(repair-jobs|shoe-repair-jobs|auto-key-jobs)/([0-9a-fA-F-]{36})(?:/(status|note))?$").matchEntire(path) ?: return null
    UUID.fromString(match.groupValues[2])
    val family = match.groupValues[1]; val action = match.groupValues[3]
    val method = row.legacyString("method")?.uppercase() ?: return null
    if(!(method == "POST" && action in listOf("status", "note") && !(family == "auto-key-jobs" && action == "note") || method == "PATCH" && family == "auto-key-jobs" && action.isBlank())) return null
    var body = JsonParser.parseString(row.legacyString("body") ?: return null)
    // Axios may already have serialised config.data before the queue's JSON.stringify.
    if(body.isJsonPrimitive && body.asJsonPrimitive.isString) body = JsonParser.parseString(body.asString)
    if(!body.isJsonObject) return null
    val objectBody = body.asJsonObject
    val allowed = when { action == "status" -> setOf("status", "note", "customer_note"); action == "note" -> setOf("note"); else -> setOf("tech_notes") }
    if(objectBody.keySet().isEmpty() || objectBody.keySet().any { it !in allowed } || objectBody.entrySet().any { !it.value.isJsonNull && (!it.value.isJsonPrimitive || !it.value.asJsonPrimitive.isString) }) return null
    if(action == "status" && objectBody.legacyString("status").isNullOrBlank()) return null
    if(action == "note" && objectBody.legacyString("note").isNullOrBlank()) return null
    if(row.legacyString("idempotencyKey").isNullOrBlank() || row.legacyString("id").isNullOrBlank()) return null
    UUID.fromString(row.legacyString("idempotencyKey")); UUID.fromString(row.legacyString("id"))
    row.legacyString("expectedUpdatedAt")?.takeIf { it.isNotBlank() }?.let { if(it.any { c -> c.isISOControl() } || it.length > 80) return null }
    LegacyWriteTarget("v1/$family/${match.groupValues[2]}", path, method, objectBody, match.groupValues[2])
}.getOrNull() }

/** Separate encrypted archive: signing out clears native work, but must not erase the old app's recovery backup. */
object LegacyRecoveryStore {
    private var cached: android.content.SharedPreferences? = null
    @Synchronized private fun prefs(context: Context): android.content.SharedPreferences {
        cached?.let { return it }
        val app = context.applicationContext
        val key = MasterKey.Builder(app).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
        return EncryptedSharedPreferences.create(app, "mainspring_legacy_recovery", key, EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV, EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM).also { cached = it }
    }
    private fun metadata(context: Context) = context.applicationContext.getSharedPreferences("mainspring_legacy_recovery_meta", Context.MODE_PRIVATE)
    fun scanned(context: Context): Boolean = metadata(context).getBoolean("scanned-v1", false)
    fun snapshot(context: Context): JsonObject? = prefs(context).getString("snapshot", null)?.let { runCatching { JsonParser.parseString(it).asJsonObject }.getOrNull() }
    @SuppressLint("ApplySharedPref") fun save(context: Context, json: String) {
        require(json.length <= 20 * 1024 * 1024) { "The previous app has a large amount of saved work. It remains untouched; contact support for recovery." }
        val snapshot = JsonParser.parseString(json).asJsonObject
        require(snapshot.legacyString("origin") == "https://localhost") { "Unexpected previous-app storage origin." }
        val previous = LegacyRecoveryStore.snapshot(context)
        if(previous != null) for(group in listOf("drafts", "queue", "dead")) {
            val all = previous.legacyObjects(group) + snapshot.legacyObjects(group)
            val unique = all.distinctBy { if(group == "drafts") it.legacyString("key").orEmpty() + it.legacyString("value").orEmpty() else it.legacyString("id").orEmpty() + it.legacyString("body").orEmpty() + it.legacyString("url").orEmpty() }
            snapshot.add(group, com.google.gson.JsonArray().apply { unique.forEach { add(it) } })
        }
        val merged = snapshot.toString()
        require(merged.length <= 20 * 1024 * 1024) { "The combined recovery archive is large. Existing work remains preserved; contact support for recovery." }
        check(prefs(context).edit().putString("snapshot", merged).commit()) { "Could not preserve previous app work. Free device storage and retry." }
        check(metadata(context).edit().putBoolean("scanned-v1", true).putBoolean("has-work-v1", listOf("drafts", "queue", "dead").any { snapshot.legacyObjects(it).isNotEmpty() }).commit()) { "Previous work is preserved, but its recovery marker could not be saved. Retry recovery." }
    }
    fun hasWork(context: Context): Boolean = metadata(context).getBoolean("has-work-v1", false)

}

/**
 * Opens the same default WebView profile and HTTPS origin used by Capacitor. This page only reads local storage;
 * no old app bundle runs, no TTL sweep occurs, and every network request/navigation is blocked.
 */
@SuppressLint("SetJavaScriptEnabled")
fun scanLegacyWork(context: Context, onComplete: (Result<Unit>) -> Unit) {
    val handler = Handler(Looper.getMainLooper())
    handler.post {
        val finished = AtomicBoolean(false)
        var web: WebView? = null
        lateinit var finish: (Result<String>) -> Unit
        finish = { result -> handler.post {
            if(finished.compareAndSet(false, true)) {
                web?.removeJavascriptInterface("MainspringRecovery"); web?.stopLoading(); web?.destroy(); web = null
                CoroutineScope(Dispatchers.IO).launch {
                    val saved = result.mapCatching { LegacyRecoveryStore.save(context.applicationContext, it) }
                    withContext(Dispatchers.Main) { onComplete(saved) }
                }
            }
        } }
        try {
            val html = """<!doctype html><meta charset="utf-8"><title>Previous app recovery</title><script>
            (async function(){
              const drafts=[];
              for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key && key.startsWith('mainspring.draft.')) drafts.push({key,value:localStorage.getItem(key)});}
              const stored=await new Promise((resolve,reject)=>{
                let absent=false; const request=indexedDB.open('mainspring-offline');
                request.onupgradeneeded=()=>{absent=true;request.transaction.abort();};
                request.onerror=()=>{if(absent)resolve({queue:[],dead:[]});else reject(new Error('Could not read saved offline work'));};
                request.onblocked=()=>reject(new Error('Previous app storage is busy. Close other app windows and retry.'));
                request.onsuccess=()=>{const db=request.result;const names=['queue','dead'].filter(n=>db.objectStoreNames.contains(n));
                  if(!names.length){db.close();resolve({queue:[],dead:[]});return;}
                  const tx=db.transaction(names,'readonly');const rows={queue:[],dead:[]};
                  names.forEach(n=>{const r=tx.objectStore(n).getAll();r.onsuccess=()=>{rows[n]=r.result;};});
                  tx.oncomplete=()=>{db.close();resolve(rows);};tx.onerror=()=>{db.close();reject(new Error('Could not read saved offline work'));};
                };
              });
              MainspringRecovery.success(JSON.stringify({version:1,origin:location.origin,capturedAt:Date.now(),drafts,queue:stored.queue,dead:stored.dead}));
            })().catch(e=>MainspringRecovery.failure(String(e.message||e)));
            </script>""".trimIndent()
            web = WebView(context).apply {
                settings.javaScriptEnabled = true; settings.domStorageEnabled = true
                settings.allowFileAccess = false; settings.allowContentAccess = false
                addJavascriptInterface(object {
                    @JavascriptInterface fun success(json: String) { finish(Result.success(json)) }
                    @JavascriptInterface fun failure(message: String) { finish(Result.failure(IllegalStateException(message.take(300)))) }
                }, "MainspringRecovery")
                webViewClient = object: WebViewClient() {
                    override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean = request?.url?.toString() != "https://localhost/__native_migration__"
                    override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse {
                        val body = if(request?.url?.toString() == "https://localhost/__native_migration__") html else ""
                        return WebResourceResponse("text/html", "UTF-8", ByteArrayInputStream(body.toByteArray(Charsets.UTF_8)))
                    }
                }
                loadUrl("https://localhost/__native_migration__")
            }
            handler.postDelayed({ if(!finished.get()) finish(Result.failure(IllegalStateException("Could not finish checking previous app work. It remains untouched; retry recovery."))) }, 30_000)
        } catch(e: Exception) { finish(Result.failure(e)) }
    }
}
