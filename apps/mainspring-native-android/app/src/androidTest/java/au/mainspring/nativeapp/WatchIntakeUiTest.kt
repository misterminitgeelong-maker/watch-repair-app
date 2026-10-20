package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.MainspringTheme
import androidx.compose.ui.graphics.asAndroidBitmap
import android.graphics.Bitmap
import androidx.core.content.FileProvider
import java.io.File
import com.google.gson.JsonParser
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.SavedStateHandle
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.screens.WatchIntakeScreen
import au.mainspring.nativeapp.ui.screens.ShoeIntakeScreen
import au.mainspring.nativeapp.ui.screens.MobileIntakeScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.atomic.AtomicInteger

/** Exercises native controls against a local fake API, never production records or SMS. */
class WatchIntakeUiTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val jobs = AtomicInteger()
    private val uploads = AtomicInteger()
    private val jobBodies = java.util.concurrent.ConcurrentLinkedQueue<String>()
    private var failPhotoOnce = false
    private val shoeJobs = AtomicInteger(); private val shoeLinks = AtomicInteger(); private val mobileJobs = AtomicInteger()
    @Before fun setup() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        TokenStore.init(context); TokenStore.clear()
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty().substringBefore('?')
                val body = when {
                    path == "/v1/watch-catalogue/repairs-config" -> "{\"combos\":[],\"currency\":\"AUD\"}"
                    request.method == "GET" -> "[]"
                    path == "/v1/customers" -> "{\"id\":\"customer-1\",\"full_name\":\"Avery\",\"tenant_id\":\"tenant-1\",\"created_at\":\"2026-10-07\"}"
                    path == "/v1/watches" -> "{\"id\":\"watch-1\",\"customer_id\":\"customer-1\",\"tenant_id\":\"tenant-1\"}"
                    path == "/v1/shoe-repair-jobs/shoes" -> "{\"id\":\"shoe-1\"}"
                    path == "/v1/shoe-repair-jobs" -> { shoeJobs.incrementAndGet(); "{\"id\":\"shoe-job\",\"items\":[]}" }
                    path == "/v1/shoe-repair-jobs/shoe-job/shoes" -> { shoeLinks.incrementAndGet(); "{\"id\":\"shoe-job\",\"items\":[]}" }
                    path == "/v1/auto-key-jobs" -> { mobileJobs.incrementAndGet(); jobBodies.add(request.body.readUtf8()); "{\"id\":\"mobile-job\"}" }
                    path == "/v1/repair-jobs" -> { val n = jobs.incrementAndGet(); jobBodies.add(request.body.readUtf8()); "{\"id\":\"job-$n\",\"watch_id\":\"watch-1\",\"job_number\":\"W00$n\",\"title\":\"Battery\",\"status\":\"awaiting_quote\",\"priority\":\"normal\",\"tenant_id\":\"tenant-1\",\"created_at\":\"2026-10-07\"}" }
                    path == "/v1/attachments" -> { val n = uploads.incrementAndGet()
                        if(failPhotoOnce && n == 1) return MockResponse().setResponseCode(503)
                        "{\"id\":\"photo-1\",\"tenant_id\":\"tenant-1\",\"storage_key\":\"photo.jpg\",\"file_name\":\"photo.jpg\",\"content_type\":\"image/jpeg\",\"file_size_bytes\":100,\"created_at\":\"2026-10-07\"}" }
                    else -> return MockResponse().setResponseCode(404)
                }
                return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
            }
        }
        server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString())
        TokenStore.setDraftScope("test-tenant", "test-user")
        TokenStore.setCalendarTimezone("Australia/Sydney")
        TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    @Test fun newCustomerQuickJobCompletesAndOnlyCreatesOneTicket() {
        val vm = WatchIntakeViewModel(SavedStateHandle())
        compose.setContent { MainspringTheme { WatchIntakeScreen(onBack = {}, onOpenJob = {}, vm = vm) } }
        compose.onNodeWithText("New Customer").performClick()
        compose.onNode(hasContentDescription("Full Name *") and hasSetTextAction()).performTextInput("Avery")
        compose.onNodeWithText("Next →").performClick()
        compose.onNodeWithText("Quick counter job (photos optional)").performScrollTo()
        compose.onAllNodes(isToggleable()).onLast().performClick()
        Assert.assertEquals("true", vm.field("quickJob"))
        compose.onNodeWithText("Next →").performClick()
        compose.onNode(hasContentDescription("Job Title *") and hasSetTextAction()).performScrollTo().performTextInput("Battery")
        compose.onNodeWithText("Next →").performClick()
        compose.onNodeWithText("Create Job Ticket").assertIsEnabled()
            .performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.OnClick) { it() }
        compose.waitUntil(15_000) { vm.state.value.complete || (!vm.state.value.busy && vm.state.value.error != null) }
        Assert.assertNull(vm.state.value.error)
        compose.onNodeWithText("Open Watch 1", substring = true).assertExists()  // now also shows the ticket number
        Assert.assertEquals(1, jobs.get())
        screenshot("quick-job-complete.png")
    }
    private fun screenshot(name: String) {
        if (android.os.Build.VERSION.SDK_INT < 29) return
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val values = android.content.ContentValues().apply {
            put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, name)
            put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/png")
            put(android.provider.MediaStore.Images.Media.RELATIVE_PATH, "Pictures/Mainspring-native-QA")
            put(android.provider.MediaStore.Images.Media.IS_PENDING, 1)
        }
        val uri = context.contentResolver.insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)!!
        context.contentResolver.openOutputStream(uri)!!.use { compose.onRoot().captureToImage().asAndroidBitmap().compress(Bitmap.CompressFormat.PNG, 100, it) }
        context.contentResolver.update(uri, android.content.ContentValues().apply { put(android.provider.MediaStore.Images.Media.IS_PENDING, 0) }, null, null)
    }
    @Test fun multiWatchDraftSurvivesNewViewModelAndUsesMatchingTicketFields() {
        val fields = WatchIntakeViewModel(SavedStateHandle())
        fields.setField("customerId", "existing-customer"); fields.setField("title", "Battery")
        fields.setField("watchCount", "2"); fields.setField("deposit", "15.25")
        fields.setField("collection", "09/10/2026"); fields.setField("step", "3")
        val restored = WatchIntakeViewModel(SavedStateHandle())
        Assert.assertEquals("Battery", restored.field("title"))
        Assert.assertEquals(2, restored.count())
        compose.setContent { MainspringTheme { WatchIntakeScreen(onBack = {}, onOpenJob = {}, vm = restored) } }
        compose.onNodeWithText("Create 2 Tickets").performClick()
        compose.waitUntil(15_000) { compose.onAllNodesWithText("Intake complete").fetchSemanticsNodes().isNotEmpty() }
        Assert.assertEquals(2, jobs.get())
        jobBodies.forEach { body -> val json = JsonParser.parseString(body).asJsonObject
            Assert.assertEquals(1525, json["deposit_cents"].asInt)
            Assert.assertEquals("2026-10-09", json["collection_date"].asString)
        }
        screenshot("multi-watch-complete.png")
    }
    @Test fun failedPhotoRetryKeepsSameJob() {
        failPhotoOnce = true
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val directory = File(context.filesDir, "intake-photos").apply { mkdirs() }
        val file = File(directory, "test-photo.jpg")
        file.outputStream().use { Bitmap.createBitmap(16, 16, Bitmap.Config.ARGB_8888).compress(Bitmap.CompressFormat.JPEG, 90, it) }
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.intake", file)
        val vm = WatchIntakeViewModel(SavedStateHandle())
        vm.setField("customerId", "customer-1"); vm.setField("title", "Battery")
        vm.setField("quickJob", "true"); vm.setField("step", "3"); vm.setPhoto(0, "front", uri.toString())
        compose.setContent { MainspringTheme { WatchIntakeScreen(onBack = {}, onOpenJob = {}, vm = vm) } }
        compose.onNodeWithText("Create Job Ticket").performClick()
        compose.waitUntil(15_000) { vm.state.value.complete && vm.state.value.uploadFailures.isNotEmpty() }
        compose.onNodeWithText("Continue / retry remaining photos").performScrollTo().performClick()
        compose.waitUntil(15_000) { vm.state.value.complete && !vm.state.value.busy && vm.state.value.uploadFailures.isEmpty() }
        Assert.assertEquals(1, jobs.get()); Assert.assertEquals(2, uploads.get())
        Assert.assertEquals("", vm.photo(0, "front"))
    }
    @Test fun multipleShoePairsCreateOneJobAndLinkExtraPair() {
        val vm = ShoeIntakeViewModel(SavedStateHandle())
        vm.set("customerId", "customer-1"); vm.set("count", "2"); vm.set("title", "Heel repairs"); vm.set("step", "3")
        compose.setContent { MainspringTheme { ShoeIntakeScreen(onBack = {}, onOpenJob = {}, vm = vm) } }
        compose.onNodeWithText("Create Shoe Repair").performClick()
        compose.waitUntil(15_000) { vm.state.value.complete && !vm.state.value.busy }
        Assert.assertEquals(1, shoeJobs.get()); Assert.assertEquals(1, shoeLinks.get())
        compose.onNodeWithText("Open repair job").assertExists()
        screenshot("shoe-intake-complete.png")
    }
    @Test fun mobileBookingUsesShopTimezone() {
        val vm = MobileIntakeViewModel(SavedStateHandle())
        vm.set("customerId", "customer-1"); vm.set("title", "Replacement key"); vm.set("scheduled", "09/10/2026 09:30")
        vm.set("quantity", "2"); vm.set("step", "2")
        compose.setContent { MainspringTheme { MobileIntakeScreen(onBack = {}, onOpenJob = {}, vm = vm) } }
        compose.onNodeWithText("Create job").performClick()
        compose.waitUntil(15_000) { vm.field("jobId").isNotBlank() && !vm.state.value.busy }
        Assert.assertEquals(1, mobileJobs.get())
        val json = JsonParser.parseString(jobBodies.last()).asJsonObject
        Assert.assertEquals("2026-10-09T09:30+11:00", json["scheduled_at"].asString)
        Assert.assertEquals(2, json["key_quantity"].asInt)
        screenshot("mobile-intake-complete.png")
    }
}
