package au.mainspring.nativeapp

import android.webkit.WebView
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.AutoKeyJobRead
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.OpenStreetStopMap
import com.google.gson.Gson
import com.google.gson.JsonObject
import org.junit.*
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Exercises the actual bundled renderer with tile networking blocked and synthetic geocodes only. */
class RouteMapFallbackTest {
    @get:Rule val compose = createComposeRule()
    private var web: WebView? = null
    @Before fun setup() { TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear(); TokenStore.setDraftScope("map-shop", "map-user") }
    @After fun cleanup() { TokenStore.clear() }
    private fun job(id: String, title: String, address: String) = Gson().fromJson(JsonObject().apply { addProperty("id", id); addProperty("job_number", id); addProperty("title", title); addProperty("job_address", address); addProperty("status", "booking_confirmed") }, AutoKeyJobRead::class.java)
    private fun evaluate(script: String): String {
        val latch = CountDownLatch(1); var result = ""
        InstrumentationRegistry.getInstrumentation().runOnMainSync { web?.evaluateJavascript(script) { result = it; latch.countDown() } ?: latch.countDown() }
        latch.await(3, TimeUnit.SECONDS); return result
    }
    @Test fun noKeyMapShowsRealPinsAndPopupTextWithoutExecutingCustomerMarkup() {
        var opened = ""; var directions = ""
        val jobs = listOf(job("job-1", "<img src=x onerror=window.bad=true>", "1 Test Street"), job("job-2", "Second stop", "2 Test Street"))
        compose.setContent { MainspringTheme { OpenStreetStopMap(jobs, Modifier.fillMaxWidth().height(300.dp), { if(it.startsWith("1")) -37.8 to 145.0 else -37.81 to 145.02 }, { opened = it }, { directions = it }, allowTileNetwork = false, onWebView = { web = it }) } }
        compose.waitUntil(15_000) { evaluate("document.documentElement.getAttribute('data-stops')") == "\"2\"" }
        compose.onNodeWithTag("osm-map-location-count").assertTextContains("2 of 2 stops located", substring = true)
        evaluate("document.querySelector('.leaflet-marker-icon').click(); true")
        Assert.assertEquals("0", evaluate("document.querySelectorAll('.leaflet-popup-content img').length"))
        Assert.assertEquals("false", evaluate("window.bad === true"))
        Assert.assertTrue(evaluate("document.querySelector('.leaflet-popup-content').textContent").contains("onerror=window.bad"))
        evaluate("document.querySelector('.leaflet-popup-content button').click(); true")
        compose.waitUntil(5_000) { opened == "job-1" }
        evaluate("document.querySelectorAll('.leaflet-popup-content button')[1].click(); true")
        compose.waitUntil(5_000) { directions == "1 Test Street" }
        Assert.assertTrue(evaluate("!!document.querySelector('.leaflet-control-zoom-in') && !!document.querySelector('.map-fit')").contains("true"))
    }
    @Test fun unlocatedStopsAreNotInventedAndOldAccountMapCallbacksAreRejected() {
        var opened = ""
        val jobs = listOf(job("job-1", "Synthetic stop", "Unknown Test Street"))
        compose.setContent { MainspringTheme { OpenStreetStopMap(jobs, Modifier.fillMaxWidth().height(300.dp), { null }, { opened = it }, {}, allowTileNetwork = false, onWebView = { web = it }) } }
        compose.waitUntil(15_000) { evaluate("document.documentElement.getAttribute('data-stops')") == "\"0\"" }
        compose.onNodeWithTag("osm-map-location-count").assertTextContains("0 of 1 stops located", substring = true)
        TokenStore.setDraftScope("other-shop", "other-user")
        evaluate("MainspringMap.openJob('job-1'); true")
        compose.waitForIdle(); Assert.assertEquals("", opened)
    }
}
