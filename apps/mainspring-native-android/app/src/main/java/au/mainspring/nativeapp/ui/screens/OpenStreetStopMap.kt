package au.mainspring.nativeapp.ui.screens

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.webkit.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.AutoKeyJobRead
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ensureActive
import java.io.ByteArrayInputStream

/** Existing Leaflet/OSM renderer, bundled locally: no map API key and no remotely loaded executable code. */
@SuppressLint("SetJavaScriptEnabled")
@Composable fun OpenStreetStopMap(jobs: List<AutoKeyJobRead>, modifier: Modifier = Modifier,
    geocode: suspend (String) -> Pair<Double, Double>?, onJob: (String) -> Unit, onNavigate: (String) -> Unit,
    allowTileNetwork: Boolean = true, onWebView: ((WebView) -> Unit)? = null) {
    val context = LocalContext.current
    val generation = remember { TokenStore.sessionGeneration() }
    val scope = remember { TokenStore.offlineScope() }
    val currentJobs by rememberUpdatedState(jobs)
    val openJobCallback by rememberUpdatedState(onJob)
    val navigateCallback by rememberUpdatedState(onNavigate)
    var pins by remember { mutableStateOf<List<RouteMapPin>>(emptyList()) }
    var resolving by remember { mutableStateOf(false) }
    var pageReady by remember { mutableStateOf(false) }
    var rendered by remember { mutableIntStateOf(-1) }
    var failure by remember { mutableStateOf<String?>(null) }
    val cache = remember { mutableMapOf<String, Pair<Double, Double>?>() }
    val sessionCurrent = { generation == TokenStore.sessionGeneration() && scope == TokenStore.offlineScope() }
    val web = remember { WebView(context).apply {
        settings.javaScriptEnabled = true; settings.domStorageEnabled = false; settings.allowFileAccess = false; settings.allowContentAccess = false
        settings.setSupportMultipleWindows(false); settings.javaScriptCanOpenWindowsAutomatically = false; settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        settings.userAgentString = settings.userAgentString + " MainspringNative/" + BuildConfig.VERSION_NAME
        CookieManager.getInstance().setAcceptThirdPartyCookies(this, false)
        addJavascriptInterface(object {
            @JavascriptInterface fun ready(count: Int) { post { if(sessionCurrent()) rendered = count.coerceIn(0, 100) } }
            @JavascriptInterface fun openJob(id: String) { post { if(sessionCurrent() && currentJobs.any { it.id == id }) openJobCallback(id) } }
            @JavascriptInterface fun navigate(id: String) { post { if(sessionCurrent()) currentJobs.firstOrNull { it.id == id }?.jobAddress?.takeIf(String::isNotBlank)?.let(navigateCallback) } }
        }, "MainspringMap")
        webViewClient = object: WebViewClient() {
            override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
                val raw = request?.url?.toString().orEmpty()
                val asset = if(request?.method == "GET") routeMapLocalAsset(raw) else null
                if(asset != null) {
                    val mime = when { asset.endsWith(".js") -> "application/javascript"; asset.endsWith(".css") -> "text/css"; else -> "text/html" }
                    return WebResourceResponse(mime, "UTF-8", context.assets.open(asset))
                }
                if(allowTileNetwork && request?.method == "GET" && !request.isForMainFrame && isRouteMapTileUrl(raw)) return null
                return WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", emptyMap(), ByteArrayInputStream(ByteArray(0)))
            }
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                if(request?.isForMainFrame == true && request.hasGesture() && request.url.toString() == "https://www.openstreetmap.org/copyright") {
                    post { try { context.startActivity(Intent(Intent.ACTION_VIEW, request.url)) } catch(_: Exception) { failure = "No browser is available for map attribution." } }
                }
                return true
            }
            override fun onPageFinished(view: WebView?, url: String?) { if(url == "$ROUTE_MAP_ORIGIN/" && sessionCurrent()) pageReady = true }
        }
        loadUrl("$ROUTE_MAP_ORIGIN/")
    } }
    DisposableEffect(web) { onWebView?.invoke(web); onDispose { web.removeJavascriptInterface("MainspringMap"); web.stopLoading(); web.destroy() } }
    LaunchedEffect(jobs.map { it.id to it.jobAddress }) {
        resolving = true; pins = emptyList()
        try {
            val addresses = jobs.mapNotNull { it.jobAddress?.trim()?.takeIf(String::isNotBlank) }.distinct().take(50)
            for(address in addresses) { ensureActive(); if(!cache.containsKey(address)) cache[address] = try { geocode(address) } catch(e: CancellationException) { throw e } catch(_: Exception) { null } }
            pins = jobs.mapIndexedNotNull { index, job -> cache[job.jobAddress?.trim()]?.let { (lat, lng) -> RouteMapPin(job.id, "${job.jobNumber} · ${job.title}", job.jobAddress.orEmpty(), au.mainspring.nativeapp.ui.statusLabel(job.status), index + 1, lat, lng) } }.take(100)
        } finally { resolving = false }
    }
    LaunchedEffect(pageReady, pins) { if(pageReady && sessionCurrent()) web.evaluateJavascript("window.renderStops(${routeMapPayload(pins)});", null) }
    Box(modifier.testTag("osm-route-map")) {
        AndroidView(factory = { web }, modifier = Modifier.fillMaxSize())
        if(!pageReady || rendered < 0) LinearProgressIndicator(Modifier.fillMaxWidth().align(Alignment.TopCenter))
        Surface(Modifier.align(Alignment.BottomStart).padding(start = 8.dp, bottom = 22.dp), color = MaterialTheme.colorScheme.surface) {
            Text(if(resolving) "Locating stops…" else "${pins.size} of ${jobs.size} stops located · lines show stop order", Modifier.padding(6.dp).testTag("osm-map-location-count"), style = MaterialTheme.typography.labelSmall)
        }
        if(!resolving && jobs.isNotEmpty() && pins.isEmpty()) Surface(Modifier.align(Alignment.Center).padding(16.dp), color = MaterialTheme.colorScheme.surface) { Text("Addresses could not be located. Use the stop list for exact addresses and navigation.", Modifier.padding(10.dp), style = MaterialTheme.typography.bodySmall) }
        failure?.let { Surface(Modifier.align(Alignment.TopCenter).padding(8.dp)) { Text(it, Modifier.padding(8.dp), style = MaterialTheme.typography.bodySmall) } }
    }
}
