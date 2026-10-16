package au.mainspring.nativeapp.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AttachmentRead
import au.mainspring.nativeapp.api.absolutizeApiUrl
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit

/** Normalises the API's several spellings of the three services to "watch", "shoe" or "auto_key". */
fun jobServiceKey(service: String): String = when(service.lowercase().replace('-', '_')) {
    "watch", "repair_jobs", "repair" -> "watch"
    "shoe", "shoe_repair_jobs", "shoes" -> "shoe"
    else -> "auto_key"
}

/** Small line icon for the kind of job: watch, shoe, or key. Decorative; the row text already names the job. */
@Composable fun JobTypeMark(service: String, modifier: Modifier = Modifier, size: Dp = 18.dp,
    color: Color = MaterialTheme.colorScheme.onSurfaceVariant) {
    val kind = jobServiceKey(service)
    Canvas(modifier.size(size)) {
        val s = this.size.width / 24f
        val w = 1.6f * s
        fun p(x: Float, y: Float) = Offset(x * s, y * s)
        fun line(x1: Float, y1: Float, x2: Float, y2: Float) = drawLine(color, p(x1, y1), p(x2, y2), w, StrokeCap.Round)
        when(kind) {
            "watch" -> {
                drawCircle(color, 5.5f * s, p(12f, 12f), style = Stroke(w))
                line(12f, 12f, 12f, 9f); line(12f, 12f, 14.2f, 13.2f)
                line(9.5f, 6.5f, 10.2f, 2.5f); line(14.5f, 6.5f, 13.8f, 2.5f); line(10.2f, 2.5f, 13.8f, 2.5f)
                line(9.5f, 17.5f, 10.2f, 21.5f); line(14.5f, 17.5f, 13.8f, 21.5f); line(10.2f, 21.5f, 13.8f, 21.5f)
            }
            "shoe" -> {
                val path = Path().apply {
                    moveTo(3f * s, 16f * s); lineTo(3f * s, 8f * s); lineTo(8f * s, 8f * s)
                    cubicTo(9f * s, 11f * s, 12f * s, 12f * s, 16f * s, 13f * s)
                    cubicTo(19f * s, 14f * s, 21f * s, 14.5f * s, 21f * s, 16f * s)
                    close()
                }
                drawPath(path, color, style = Stroke(w, cap = StrokeCap.Round, join = androidx.compose.ui.graphics.StrokeJoin.Round))
                line(3f, 19f, 21f, 19f); line(10.5f, 10.2f, 12f, 8.6f)
            }
            else -> {
                drawCircle(color, 4f * s, p(7.5f, 12f), style = Stroke(w))
                line(11.5f, 12f, 21f, 12f); line(17f, 12f, 17f, 15.5f); line(20f, 12f, 20f, 14.5f)
            }
        }
    }
}

/** Soft tinted square used behind placeholders; mint in light, deep forest in dark. */
@Composable private fun placeholderTint(): Color =
    if(LocalCalibre.current) { if(isSystemInDarkTheme()) Calibre.DarkForestContainer else Calibre.ForestMint } else MaterialTheme.colorScheme.surfaceVariant

/**
 * In-memory job photo source. A job's first intake photo is looked up lazily (one list call, one link, one download),
 * limited to three concurrent fetches, with positive and negative results cached so scrolling never repeats work.
 * Everything is dropped when the session changes. A missing photo or any failure is simply "no photo".
 */
object JobPhotoStore {
    private val cache = object : LruCache<String, Bitmap>(24 * 1024 * 1024) { override fun sizeOf(key: String, value: Bitmap) = value.byteCount }
    private val keys = ConcurrentHashMap<String, String>()          // jobKey -> storage key, "" when the job has no photo
    private val failedAt = ConcurrentHashMap<String, Long>()        // transient failures retried after a pause
    private val gate = Semaphore(3)
    @Volatile private var generation = -1L
    private const val RETRY_AFTER_MS = 60_000L
    private const val MAX_BYTES = 8 * 1024 * 1024

    private val http: OkHttpClient by lazy { OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS).readTimeout(20, TimeUnit.SECONDS).build() }

    private fun checkSession() {
        val g = TokenStore.sessionGeneration()
        if(g != generation) synchronized(this) {
            if(g != generation) { cache.evictAll(); keys.clear(); failedAt.clear(); generation = g }
        }
    }

    private fun jobKey(service: String, jobId: String) = "${jobServiceKey(service)}/$jobId"

    /** The first image among [files] (oldest first, which is the intake photo), or null. */
    fun firstImage(files: List<AttachmentRead>): AttachmentRead? =
        files.filter { it.contentType?.startsWith("image/") != false }.minByOrNull { it.createdAt }

    /** Tells the store a screen already knows the job's attachments, saving the list call. */
    fun learn(service: String, jobId: String, files: List<AttachmentRead>) {
        checkSession(); keys[jobKey(service, jobId)] = firstImage(files)?.storageKey.orEmpty()
    }

    /** Cached bitmap only (no I/O); null if not loaded yet or no photo. */
    fun peek(service: String, jobId: String, maxPx: Int): Bitmap? {
        checkSession()
        val storage = keys[jobKey(service, jobId)]?.takeIf { it.isNotEmpty() } ?: return null
        return cache.get("$storage@$maxPx")
    }

    /** True when the job is known to have no photo, so callers can skip loading. */
    fun knownEmpty(service: String, jobId: String): Boolean { checkSession(); return keys[jobKey(service, jobId)] == "" }

    suspend fun load(service: String, jobId: String, maxPx: Int): Bitmap? {
        checkSession()
        val jk = jobKey(service, jobId)
        peek(service, jobId, maxPx)?.let { return it }
        if(keys[jk] == "") return null
        failedAt[jk]?.let { if(System.currentTimeMillis() - it < RETRY_AFTER_MS) return null }
        return try {
            gate.withPermit {
                checkSession()
                peek(service, jobId, maxPx)?.let { return@withPermit it }
                val api = ApiClient.api
                val storage = keys[jk] ?: run {
                    val files = when(jobServiceKey(service)) {
                        "watch" -> api.listAttachments(repairJobId = jobId, limit = 20)
                        "shoe" -> api.listAttachments(shoeRepairJobId = jobId, limit = 20)
                        else -> api.listAttachments(autoKeyJobId = jobId, limit = 20)
                    }
                    firstImage(files)?.storageKey.orEmpty().also { keys[jk] = it }
                }
                if(storage.isEmpty()) return@withPermit null
                val base = ApiClient.getEffectiveBaseUrl()
                val url = absolutizeApiUrl(base, api.getAttachmentDownloadLink(storage).downloadUrl)
                val bitmap = withContext(Dispatchers.IO) { download(url, base, maxPx) }
                if(bitmap != null) cache.put("$storage@$maxPx", bitmap) else failedAt[jk] = System.currentTimeMillis()
                bitmap
            }
        } catch(e: CancellationException) { throw e }
        catch(_: Exception) { failedAt[jk] = System.currentTimeMillis(); null }
    }

    private fun download(url: String, base: String, maxPx: Int): Bitmap? {
        val request = Request.Builder().url(url).apply {
            // Only our own API gets the bearer token; signed storage links are fetched as they are.
            val own = try { java.net.URI(url).host == java.net.URI(base).host } catch(_: Exception) { false }
            val token = TokenStore.sessionSnapshot().access
            if(own && token != null) header("Authorization", "Bearer $token")
        }.build()
        http.newCall(request).execute().use { response ->
            if(!response.isSuccessful) return null
            val body = response.body ?: return null
            if(body.contentLength() > MAX_BYTES) return null
            val bytes = body.byteStream().use { input ->
                val out = java.io.ByteArrayOutputStream(); val buf = ByteArray(16 * 1024); var total = 0
                while(true) { val n = input.read(buf); if(n < 0) break; total += n; if(total > MAX_BYTES) return null; out.write(buf, 0, n) }
                out.toByteArray()
            }
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
            if(bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
            var sample = 1
            while(bounds.outWidth / (sample * 2) >= maxPx && bounds.outHeight / (sample * 2) >= maxPx) sample *= 2
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
        }
    }
}

/** Rounded job-row thumbnail: the first intake photo, else the job-type icon on a soft tint. Never shows an error. */
@Composable fun JobThumb(service: String, jobId: String, modifier: Modifier = Modifier, size: Dp = 52.dp) {
    val px = with(androidx.compose.ui.platform.LocalDensity.current) { size.roundToPx() }.coerceAtLeast(64)
    var bitmap by remember(service, jobId) { mutableStateOf(JobPhotoStore.peek(service, jobId, px)) }
    LaunchedEffect(service, jobId, px) { if(bitmap == null) bitmap = try { JobPhotoStore.load(service, jobId, px) } catch(e: CancellationException) { throw e } catch(_: Exception) { null } }
    val shape = RoundedCornerShape(10.dp)
    Box(modifier.size(size).clip(shape).background(placeholderTint()), contentAlignment = Alignment.Center) {
        val b = bitmap
        if(b != null) Image(b.asImageBitmap(), contentDescription = null, modifier = Modifier.size(size), contentScale = ContentScale.Crop)
        else JobTypeMark(service, size = size * 0.46f, color = if(LocalCalibre.current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** 16:9 rounded photo at the top of a job summary. Renders nothing when there is no photo. Tapping calls [onClick] if given. */
@Composable fun JobHeroPhoto(service: String, jobId: String, modifier: Modifier = Modifier, known: List<AttachmentRead>? = null, onClick: (() -> Unit)? = null) {
    val maxPx = 1080
    LaunchedEffect(known) { if(known != null) JobPhotoStore.learn(service, jobId, known) }
    var bitmap by remember(service, jobId) { mutableStateOf(JobPhotoStore.peek(service, jobId, maxPx)) }
    LaunchedEffect(service, jobId, known) { if(bitmap == null) bitmap = try { JobPhotoStore.load(service, jobId, maxPx) } catch(e: CancellationException) { throw e } catch(_: Exception) { null } }
    val b = bitmap ?: return
    val click = if(onClick != null) Modifier.clickable(onClickLabel = "Open photos", role = Role.Button, onClick = onClick) else Modifier
    Image(b.asImageBitmap(), contentDescription = "Job photo", contentScale = ContentScale.Crop,
        modifier = modifier.fillMaxWidth().aspectRatio(16f / 9f).clip(RoundedCornerShape(14.dp)).then(click))
}
