package au.mainspring.nativeapp

import androidx.compose.runtime.Composable
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import au.mainspring.nativeapp.ui.screens.*
import au.mainspring.nativeapp.api.ApiClient
import androidx.test.espresso.Espresso.closeSoftKeyboard
import kotlinx.coroutines.runBlocking
import android.view.View
import android.view.ViewGroup
import android.webkit.WebView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry
import androidx.test.runner.lifecycle.Stage
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Real screens, authenticated against ReviewData.baseUrl. Preparation only opens UI: no saves,
 * messages, bookings, status changes or payments. The runner supplies a fresh view-model store
 * and saveable-state owner for each case, waits for local HTTP requests, and captures the window. */
fun mobileReviewCases(data: ReviewData): List<ReviewCase> = buildList {
    val job = data.id("mobileJob")
    val completed = data.ids["mobileCompletedJob"] ?: job
    fun capture(id: String, title: String, prepare: (ComposeContentTestRule) -> Unit = {}, content: @Composable () -> Unit) {
        add(ReviewCase("mobile-$id", title, "Mobile services", content, prepare))
    }
    fun detail() : @Composable () -> Unit = {
        AutoKeyJobDetailScreen(jobId = job, apiBaseUrl = data.baseUrl, onBack = {}, onMessages = {}, onFinance = {}, onEdit = {})
    }
    fun board() : @Composable () -> Unit = {
        MobileWorkBoardScreen(data.baseUrl, onBack = {}, onOpenJob = {}, onNewJob = {}, onNavigate = {})
    }
    fun intake() : @Composable () -> Unit = {
        MobileIntakeScreen(onBack = {}, onOpenJob = {}, preselectedCustomerId = data.ids["customer"])
    }
    capture("kanban", "Mobile Services · Kanban", content = board())
    capture("directory", "Mobile Services · job directory") { AutoKeyJobsScreen({}, {}, {}) }
    capture("filters", "Mobile job filters", prepare = { it.mobileReviewTag("filters-button").performClick() }) { AutoKeyJobsScreen({}, {}, {}) }
    listOf("focus" to "Focus", "status" to "Status", "technician" to "Technician", "category" to "Category").forEach { (key, label) ->
        capture("filters-$key-open", "Mobile job filters · $label dropdown", prepare = { rule ->
            rule.mobileReviewTag("filters-button").performClick()
            rule.mobileReviewTag("mobile-filter-$key").performScrollTo().performClick()
        }) { AutoKeyJobsScreen({}, {}, {}) }
    }
    capture("list", "Mobile Services · list", prepare = { rule ->
        rule.mobileReviewTag("view-select").performClick(); rule.mobileReviewText("List").performClick()
    }, content = board())
    capture("planner", "Mobile Services · week planner", prepare = { rule ->
        rule.mobileReviewTag("view-select").performClick(); rule.mobileReviewText("Planner").performClick()
    }, content = board())
    capture("today", "Today · mobile jobs") { TodayScreen({}, {}, {}) }
    listOf("Quotes", "Booked", "Unpaid").forEach { tab ->
        capture("today-${tab.lowercase()}", "Today · $tab", prepare = { it.mobileReviewText(tab).performClick() }) { TodayScreen({}, {}, {}) }
    }
    capture("dispatch", "Dispatch · today") { DispatchScreen({}, {}, {}, {}, {}, onOpenBookingRequests = {}, onOpenRunSheet = {}) }
    capture("run-sheet", "Today's run sheet") { TodayScreen({}, {}, {}, runSheet = true) }
    capture("route", "Route map and stop order · sample map positions", prepare = { rule ->
        rule.waitUntil(20_000) {
            rule.onAllNodesWithTag("osm-map-location-count").fetchSemanticsNodes().any { node ->
                node.config[androidx.compose.ui.semantics.SemanticsProperties.Text]
                    .any { Regex("[1-9][0-9]* of [1-9][0-9]* stops located").containsMatchIn(it.text) }
            }
        }
        // Check the real bundled Leaflet renderer and a decoded raster tile, not just its native
        // overlay. Geocodes are capture fixtures; map HTML, markers and tiles remain production code.
        rule.waitUntil(30_000) { mobileReviewMapRendered() }
        rule.waitForIdle()
        Thread.sleep(1_000) // Allow the final tile/marker animation to settle before the window capture.
    }) {
        Column(Modifier.fillMaxSize()) {
            Text("Sample map positions · public suburb centres", Modifier.padding(horizontal = 16.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall)
            Box(Modifier.weight(1f)) { RouteScreen({}, {}, geocode = ::mobileReviewCoordinates) }
        }
    }
    capture("pool", "Dispatch pool") { DispatchPoolScreen({}, {}, {}) }
    capture("intake", "New mobile job · service and customer", content = intake())
    capture("intake-job-type-open", "New mobile job · job type dropdown", prepare = { rule ->
        rule.mobileReviewTag("intake-job-type").performClick()
    }, content = intake())
    capture("intake-booking", "New mobile job · address and booking", prepare = { rule ->
        // MAINSPRING WizardField draws a small-caps label with cleared semantics; the input's
        // accessible name is contentDescription. Searching visible text can never find it.
        require(ApiClient.getEffectiveBaseUrl() == data.baseUrl)
        val sample = runBlocking { ApiClient.api.getAutoKeyJob(job) }
        rule.mobileReviewField("Job address").performScrollTo().performTextReplacement(requireNotNull(sample.jobAddress))
        val booking = requireNotNull(sample.scheduledAt) { "The screenshot job needs a booking time" }
        rule.mobileReviewField("Booking (DD/MM/YYYY HH:mm)").performScrollTo()
            .performTextReplacement(au.mainspring.nativeapp.ui.scheduleInputDate(booking, TokenStore.calendarTimezone()))
        closeSoftKeyboard()
        rule.mobileReviewField("Job address").performScrollTo()
    }, content = intake())
    capture("intake-price", "New mobile job · quoted customer price", prepare = { rule ->
        rule.mobileReviewTag("intake-manual-price").performScrollTo()
    }, content = intake())
    capture("pricing", "Mobile pricing catalogue") { MobileIntakePricingDialog({}, { _, _, _ -> }) }
    capture("detail", "Mobile job · Info", prepare = { it.mobileReviewText("Info") }, content = detail())
    listOf("Vehicle & Key", "Quotes", "Photos", "Messages", "Activity").forEachIndexed { index, tab ->
        capture("detail-${index + 1}", "Mobile job · $tab", prepare = { rule ->
            rule.mobileReviewText(tab).performScrollTo().performClick()
        }, content = detail())
    }
    capture("edit", "Edit mobile job") { MobileEditorScreen(job, {}) }
    capture("arrival", "Arrival message · unsent customer preview", prepare = { rule ->
        rule.mobileReviewText("Arrival window, e.g. 9–11 am").performTextReplacement("9–11 am")
        closeSoftKeyboard()
    }) { ArrivalMessageScreen(job, {}) }
    data.ids["mobileQuote"]?.let { quote ->
        capture("signature", "Mobile quote · recorded customer signature", prepare = { rule ->
            rule.waitUntil(20_000) {
                rule.onAllNodesWithContentDescription("Customer's recorded quote signature").fetchSemanticsNodes().isNotEmpty()
            }
        }) { QuoteSignatureScreen(job, quote, {}) }
    }
    capture("finance", "Mobile job · quote and approval") { MobileFinanceScreen(job, {}) }
    capture("invoice", "Completed mobile job · invoice") { MobileFinanceScreen(completed, {}) }
    data.ids["mobileCompletedJob"]?.let { invoiceJob ->
        capture("payment-review", "Mobile invoice · payment method review", prepare = { rule ->
            rule.mobileReviewText("Record payment").performScrollTo().performClick()
        }) { MobileFinanceScreen(invoiceJob, {}) }
    }
    capture("quote-compose", "Mobile job · new quote form", prepare = { rule ->
        rule.mobileReviewText("Create quote").performScrollTo().performClick()
    }) { MobileFinanceScreen(job, {}) }
    capture("quote-two-outcomes", "Mobile quote · two possible outcomes", prepare = { rule ->
        rule.mobileReviewText("Create quote").performScrollTo().performClick()
        rule.mobileReviewTag("quote-two-outcome").performScrollTo().performClick()
    }) { MobileFinanceScreen(job, {}) }
    capture("operations", "Mobile operations cockpit") { MobileFinanceReportScreen({}) }
    capture("report", "Mobile finance report", prepare = { it.mobileReviewText("Finance").performClick() }) { MobileFinanceReportScreen({}) }
    capture("target", "Weekly cash target editor", prepare = { rule ->
        rule.mobileReviewText("Edit weekly cash target").performScrollTo().performClick()
    }) { MobileFinanceReportScreen({}) }
    capture("revenue", "Revenue control and follow-ups") { RevenueControlScreen({}) }
    capture("booking-list", "Mobile booking requests") { BookingRequestsScreen(true, {}, {}) }
    capture("booking-create", "Request a mobile visit") { BookingRequestsScreen(true, {}, {}, initialCreate = true) }
    capture("booking-routing", "Booking request · operator and service area", prepare = { rule ->
        rule.mobileReviewText("Route by service area").performScrollTo()
    }) { BookingRequestsScreen(true, {}, {}, initialCreate = true) }
    capture("booking-send", "Send a customer booking request") { SendBookingRequestScreen({}) }
    data.ids["booking"]?.let { booking -> capture("booking-accept", "Review a booking request") { AcceptBookingScreen(booking, {}, {}) } }
    capture("booking-home", "Booking-only shop home") { BookingOnlyHomeScreen({}, data.session.shopName) }
    capture("prospects", "Mobile prospect list") { ProspectsScreen({}) }
    capture("prospects-board", "Mobile prospect board", prepare = { rule ->
        rule.mobileReviewTag("prospects-view-board").performScrollTo().performClick()
    }) { ProspectsScreen({}) }
    capture("prospect-visits", "Mobile prospect visits", prepare = { rule ->
        rule.mobileReviewTag("prospects-view-visits").performScrollTo().performClick()
    }) { ProspectsScreen({}) }
    capture("find-businesses", "Find businesses in the saved directory") { ProspectsScreen({}, initialTab = 1) }
    capture("toolkit", "Shop toolkit") { ToolkitScreen({}) }
    capture("database", "Database · GST and exports") { DatabaseScreen({}) }
    capture("catalogue", "Repair and movement catalogue") { CatalogueScreen({}) }
}

/** Wait for API-backed content instead of capturing loading placeholders. */
private fun ComposeContentTestRule.mobileReviewText(text: String, substring: Boolean = false): SemanticsNodeInteraction {
    waitUntil(20_000) { onAllNodesWithText(text, substring = substring).fetchSemanticsNodes().isNotEmpty() }
    return onAllNodesWithText(text, substring = substring).onFirst()
}

private fun ComposeContentTestRule.mobileReviewTag(tag: String): SemanticsNodeInteraction {
    waitUntil(20_000) { onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }
    return onAllNodesWithTag(tag).onFirst()
}

private fun ComposeContentTestRule.mobileReviewField(label: String): SemanticsNodeInteraction {
    waitUntil(20_000) { onAllNodesWithContentDescription(label).fetchSemanticsNodes().isNotEmpty() }
    return onAllNodesWithContentDescription(label).onFirst()
}

/** Screenshot-only coordinates. These are public suburb centres, never exact customer locations. */
private suspend fun mobileReviewCoordinates(address: String): Pair<Double, Double> = when {
    address.contains("Malvern", true) -> -37.8730 to 145.0440
    address.contains("Glen Waverley", true) -> -37.8790 to 145.1640
    address.contains("Carnegie", true) -> -37.8890 to 145.0570
    address.contains("Oakleigh", true) -> -37.9000 to 145.0900
    else -> -38.1499 to 144.3617 // Geelong city centre, for remaining synthetic review stops.
}

private fun mobileReviewMapRendered(): Boolean {
    val finished = CountDownLatch(1)
    var rendered = false
    InstrumentationRegistry.getInstrumentation().runOnMainSync {
        fun find(view: View): WebView? = when(view) {
            is WebView -> view
            is ViewGroup -> (0 until view.childCount).firstNotNullOfOrNull { find(view.getChildAt(it)) }
            else -> null
        }
        val web = ActivityLifecycleMonitorRegistry.getInstance().getActivitiesInStage(Stage.RESUMED)
            .firstNotNullOfOrNull { find(it.window.decorView) }
        if(web == null) finished.countDown()
        else web.evaluateJavascript("""
            Number(document.documentElement.getAttribute('data-stops')) > 0 &&
            document.querySelectorAll('.leaflet-marker-icon').length > 0 &&
            Array.from(document.querySelectorAll('img.leaflet-tile-loaded')).some(function(tile) {
                return tile.complete && tile.naturalWidth > 0;
            })
        """.trimIndent()) { result -> rendered = result == "true"; finished.countDown() }
    }
    return finished.await(2, TimeUnit.SECONDS) && rendered
}

/** The headless emulator can report decoded WebView tiles while its hardware surface is absent
 * from UiAutomation screenshots. Force only this review instance onto the window's software layer. */
private fun mobileReviewSoftwareMap() {
    val drawn = CountDownLatch(1)
    var listener: android.view.ViewTreeObserver.OnDrawListener? = null
    var map: WebView? = null
    val instrumentation = InstrumentationRegistry.getInstrumentation()
    instrumentation.runOnMainSync {
        fun find(view: View): WebView? = when(view) {
            is WebView -> view
            is ViewGroup -> (0 until view.childCount).firstNotNullOfOrNull { find(view.getChildAt(it)) }
            else -> null
        }
        val web = requireNotNull(ActivityLifecycleMonitorRegistry.getInstance().getActivitiesInStage(Stage.RESUMED)
            .firstNotNullOfOrNull { find(it.window.decorView) }) { "The route map WebView is not attached" }
        map = web
        web.setLayerType(View.LAYER_TYPE_SOFTWARE, null)
        val drawListener = android.view.ViewTreeObserver.OnDrawListener { drawn.countDown() }
        listener = drawListener
        web.viewTreeObserver.addOnDrawListener(drawListener)
        web.requestLayout()
        web.invalidate()
        web.rootView.invalidate()
        web.postOnAnimation { web.invalidate() }
    }
    try {
        check(drawn.await(5, TimeUnit.SECONDS)) { "The software route map did not draw a window frame" }
    } finally {
        instrumentation.runOnMainSync { listener?.let { if(map?.viewTreeObserver?.isAlive == true) map?.viewTreeObserver?.removeOnDrawListener(it) } }
    }
}
