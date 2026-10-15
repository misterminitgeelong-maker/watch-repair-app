package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.*
import au.mainspring.nativeapp.ui.screens.*
import okhttp3.mockwebserver.*
import org.junit.*
import java.time.*
import java.util.concurrent.atomic.AtomicInteger

class DesignWorkspaceTest {
    @get:Rule val compose=createComposeRule()
    private lateinit var server: MockWebServer
    private val writes=AtomicInteger()
    private var failingMove=false
    private var schedule=""
    private var version="v1"
    private var patch=""
    private var status="booking_confirmed"
    private var financeJourney=false
    private var invoicePaid=false
    private var disconnected=false
    private var lostPaymentResponse=false
    private fun invoice()="""{"id":"invoice-one","invoice_number":"INV-101","status":"${if(invoicePaid) "paid" else "unpaid"}","auto_key_quote_id":"quote-one","total_cents":27500,"subtotal_cents":25000,"tax_cents":2500,"currency":"AUD","payment_method":${if(invoicePaid) "\"card\"" else "null"}}"""
    private fun job(id: String,time: String?=null): String {
        val title=when(id) {"second"->"Spare key";"third"->"All keys lost";"unscheduled"->"Key programming";else->"Lockout - Car"}
        val customer=when(id) {"second"->"Casey Nguyen";"third"->"Jordan Lee";"unscheduled"->"Morgan Shah";else->"Avery Taylor"}
        val notes=when(id) {"second"->"Customer has one working key.";"third"->"Confirm immobiliser details.";"unscheduled"->"Booking time to confirm.";else->"Keys locked in tray."}
        return """{"id":"$id","job_number":"MS-$id","title":"$title","status":"$status","priority":"urgent","assigned_user_id":"tech","customer_name":"$customer","customer_phone":"0400000000","vehicle_make":"Toyota","vehicle_model":"Hilux","vehicle_year":2019,"job_address":"Demo address, Geelong","key_quantity":1,"programming_status":"pending","scheduled_at":${time?.let {"\"$it\""} ?: "null"},"updated_at":"$version","created_at":"2026-10-08T00:00:00Z","tech_notes":"$notes"}"""
    }
    @Before fun setup() {
        androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().targetContext.getSharedPreferences("more_usage", 0).edit().clear().commit()
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext);TokenStore.clear();TokenStore.setSessionRole("owner");TokenStore.setDraftScope("design-shop","design-user");TokenStore.setCalendarTimezone("Australia/Sydney")
        TokenStore.setShopIdentity("AUD","Native QA","Demo ABN","0400000000","Demo address")
        DesignPreferences.init(InstrumentationRegistry.getInstrumentation().targetContext)
        DesignPreferences.select(AppAppearance.WARM)
        DesignPreferences.fieldNavigation(false)
        val date=LocalDate.now(ZoneId.of("Australia/Sydney"))
        schedule="${date}T09:30:00+11:00"
        server=MockWebServer();server.dispatcher=object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val url=request.requestUrl!!;val path=url.encodedPath
                if(disconnected) return MockResponse().setResponseCode(503)
                val body=when {
                    path=="/v1/auto-key-jobs/page" -> when(url.queryParameter("focus")) {
                        "unscheduled" -> """{"items":[${job("unscheduled")}],"total":1}"""
                        "completed_unpaid" -> """{"items":[],"total":2}"""
                        else -> if(url.queryParameter("offset")=="2") """{"items":[${job("third","${date}T15:00:00+11:00")}],"total":3}""" else """{"items":[${job("second","${date}T13:00:00+11:00")},${job("first",schedule)}],"total":3}"""
                    }
                    path=="/v1/users" -> if(request.method=="POST") {writes.incrementAndGet();"""{"id":"new","full_name":"New technician","role":"tech","is_active":true}"""} else """[{"id":"tech","full_name":"Avery Technician","email":"avery@native.example.test","role":"tech","is_active":true}]"""
                    path=="/v1/reports/auto-key/commission" -> """{"technicians":[]}"""
                    path=="/v1/reports/period-summary" -> """{"period":"week","reference_date":"2026-10-08","period_start":"2026-10-05","period_end":"2026-10-11","jobs_opened":12,"watch_jobs_opened":5,"shoe_jobs_opened":3,"auto_key_jobs_opened":4,"customers_new":7,"financials":{"billed_cents":200000,"revenue_cents":123456,"cost_cents":20000,"gross_profit_cents":103456,"gross_margin_percent":83.8},"sales_funnel":{"quotes_sent":9,"quotes_approved":7,"quotes_declined":2,"approval_rate_percent":77.8},"operations":{"work_minutes":60,"avg_revenue_per_job_cents":10288}}"""
                    path=="/v1/mobile-services-pricing/meta" -> """{"enabled_categories":["vehicle_key","general_service"]}"""
                    path=="/v1/auto-key-jobs/second" -> job("second",schedule)
                    path=="/v1/auto-key-jobs/first" -> if(request.method=="PATCH") {
                        writes.incrementAndGet();patch=request.body.readUtf8();Assert.assertEquals("v1",request.getHeader("X-Expected-Updated-At"))
                        if(failingMove) return MockResponse().setResponseCode(503)
                        schedule=com.google.gson.JsonParser.parseString(patch).asJsonObject["scheduled_at"].asString;version="v2";job("first",schedule)
                    } else job("first",schedule)
                    path=="/v1/auto-key-jobs/first/status" -> {
                        writes.incrementAndGet();Assert.assertEquals(version,request.getHeader("X-Expected-Updated-At"))
                        status=com.google.gson.JsonParser.parseString(request.body.readUtf8()).asJsonObject["status"].asString
                        version="v2";job("first",schedule)
                    }
                    path=="/v1/auto-key-jobs/invoices/invoice-one" && request.method=="PATCH" -> {
                        writes.incrementAndGet();val body=com.google.gson.JsonParser.parseString(request.body.readUtf8()).asJsonObject
                        Assert.assertEquals("paid",body["status"].asString);Assert.assertEquals("card",body["payment_method"].asString)
                        invoicePaid=true;if(lostPaymentResponse) return MockResponse().setResponseCode(503);invoice()
                    }
                    path.endsWith("/attachments") -> "[]"
                    path.endsWith("/quotes") -> if(financeJourney) """[{"id":"quote-one","status":"approved","subtotal_cents":25000,"tax_cents":2500,"total_cents":27500,"currency":"AUD","line_items":[{"description":"Replacement key","quantity":1,"unit_price_cents":27500}]}]""" else "[]"
                    path.endsWith("/invoices") -> if(financeJourney && status=="work_completed") "[${invoice()}]" else "[]"
                    path.endsWith("/messages") -> "[]"
                    else -> "{}"
                }
                return MockResponse().setHeader("Content-Type","application/json").setBody(body)
            }
        };server.start();TokenStore.saveApiBaseUrl(server.url("/").toString());TokenStore.setDraftScope("design-shop","design-user")
    }
    @After fun cleanup() {TokenStore.clear();DesignPreferences.select(AppAppearance.WARM);server.shutdown()}
    @Test fun todayLoadsAllPagesSortsBookingsAndUsesServerQueueCounts() {
        val vm=TodayViewModel();compose.waitUntil(10_000) {!vm.state.value.loading}
        Assert.assertNull(vm.state.value.error);Assert.assertEquals(listOf("first","second","third"),vm.state.value.jobs.map {it.id})
        Assert.assertEquals(3,vm.state.value.todayCount);Assert.assertEquals(2,vm.state.value.unpaidCount)
        compose.setContent {MainspringTheme {TodayScreen({}, {}, {},vm,onEnRoute={})}}
        compose.onNodeWithText("Next up",ignoreCase=true).assertExists()
        saveNativeQaImage(compose.onRoot(),"design-today.png")
    }
    @Test fun nativeJobTabsShowVehicleAndFinancialWithoutLeavingJob() {
        var exits=0
        compose.setContent {MainspringTheme {AutoKeyJobDetailScreen("first",server.url("/").toString(),{exits++},{},{},{})}}
        compose.waitUntil(10_000) {compose.onAllNodesWithText("Vehicle & Key").fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Vehicle & Key").performClick();compose.onNodeWithText("Toyota Hilux").assertExists()
        saveNativeQaImage(compose.onRoot(),"design-vehicle-key.png")
        compose.onNodeWithText("Financial").performClick()
        compose.waitUntil(10_000) {compose.onAllNodes(hasText("Create quote") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Create quote").performScrollTo().performClick()
        compose.waitUntil(10_000) {compose.onAllNodesWithText("New quote").fetchSemanticsNodes().isNotEmpty()}
        Assert.assertEquals(0,exits)
        saveNativeQaImage(compose.onNodeWithTag("quote-editor"),"design-quote-sheet.png")
    }
    @Test fun ownerCanReachMoreAndThemeChoicePersistsAcrossComposition() {
        compose.setContent {MainspringTheme {MainspringAppShell("Native QA",server.url("/").toString(),{},setOf("auto_key","watch","shoe"))}}
        compose.onNodeWithTag("nav-more").performClick();compose.onNodeWithTag("more-group-settings").performClick();compose.onNodeWithTag("more-list").performScrollToNode(hasText("Atelier"))
        compose.onNodeWithText("Atelier").assertExists()
        compose.onNodeWithText("Night Workshop").performScrollTo().performClick();Assert.assertEquals(AppAppearance.NIGHT,DesignPreferences.appearance.value)
        Assert.assertEquals("NIGHT",InstrumentationRegistry.getInstrumentation().targetContext.getSharedPreferences("mainspring_appearance",0).getString("appearance",null))
        saveNativeQaImage(compose.onRoot(),"design-more-night.png")
    }
    @Test fun technicianNavigationHasMapPoolPosAndHidesTeamManagement() {
        TokenStore.setSessionRole("tech")
        compose.setContent {MainspringTheme {MainspringAppShell("Technician",server.url("/").toString(),{},setOf("auto_key"))}}
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithText("Map and today's route").assertExists();compose.onNodeWithText("Dispatch pool").assertExists();compose.onNodeWithText("POS / quick sale").assertExists()
        compose.onNodeWithText("Team").assertDoesNotExist()
    }
    @Test fun weekMoveOnlyPatchesBookingWithVersionAndUsesShopOffset() {
        val vm=WeekPlannerViewModel();compose.waitUntil(10_000) {!vm.state.value.loading}
        val row=vm.state.value.jobs.first {it.id=="first"}
        vm.move(row,"09/10/2026 11:00");compose.waitUntil(10_000) {!vm.state.value.busy && writes.get()==1}
        val fields=com.google.gson.JsonParser.parseString(patch).asJsonObject
        Assert.assertEquals(1,fields.size());Assert.assertEquals("2026-10-09T11:00+11:00",fields["scheduled_at"].asString)
    }
    @Test fun lostMoveSurvivesRecreationAndBlocksAnotherWrite() {
        failingMove=true
        val first=WeekPlannerViewModel();compose.waitUntil(10_000) {!first.state.value.loading}
        first.move(first.state.value.jobs.first {it.id=="first"},"09/10/2026 11:00")
        compose.waitUntil(10_000) {first.state.value.uncertain && !first.state.value.busy}
        val restored=WeekPlannerViewModel();Assert.assertTrue(restored.state.value.uncertain)
        compose.waitUntil(10_000) {!restored.state.value.loading};restored.move(restored.state.value.jobs.first(),"09/10/2026 12:00")
        Assert.assertEquals(1,writes.get())
    }
    @Test fun managerCannotCreateAccountFromNativeTeamWorkflow() {
        TokenStore.setSessionRole("manager");val vm=TeamViewModel();compose.waitUntil(10_000) {!vm.state.value.loading}
        vm.save(null,"New technician","new@native.example.test","test-password","tech",true,null)
        Assert.assertEquals(0,writes.get())
    }
    @Test fun quoteBundleFillsCartAndShowsExactPreview() {
        compose.setContent {MainspringTheme {androidx.compose.foundation.layout.Column {QuoteComposer("design-cart",false,true,true,currency="AUD",onSave={_,_,_->})}}}
        compose.waitUntil(10_000) {compose.onAllNodesWithText("All Keys Lost (full)").fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("All Keys Lost (full)").performClick()
        val stored=TokenStore.bindDrafts().loadMessageDraft("design-cart")
        Assert.assertTrue(stored.contains("449"));Assert.assertTrue(stored.contains("159"))
    }
    @Test fun repeatedQuickItemAddsQuantityRatherThanDuplicateCartLines() {
        compose.setContent {MainspringTheme {androidx.compose.foundation.layout.Column {QuoteComposer("quick-cart",false,true,true,quickSale=true,currency="AUD",onSave={_,_,_->})}}}
        compose.waitUntil(10_000) {compose.onAllNodesWithText("Callout \u2013 min charge").fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Callout \u2013 min charge").performClick();compose.onNodeWithText("Callout \u2013 min charge").performClick()
        val cart=com.google.gson.Gson().fromJson(TokenStore.bindDrafts().loadMessageDraft("quick-cart"),QuoteComposerDraft::class.java)
        Assert.assertEquals(1,cart.lines.size);Assert.assertEquals("2",cart.lines.single().quantity)
        Assert.assertEquals(10000,quotePreview(cart,"AUD").total)
        saveNativeQaImage(compose.onRoot(),"design-pos-cart.png")
    }
    @Test fun tabletJobDirectoryOpensDetailsAlongsideItsList() {
        Assume.assumeTrue("Requires the isolated tablet viewport",InstrumentationRegistry.getInstrumentation().targetContext.resources.configuration.screenWidthDp>=720)
        var exits=0
        compose.setContent {MainspringTheme {MobileWorkBoardScreen(server.url("/").toString(),{},{exits++},{},{})}}
        compose.onNode(hasScrollToIndexAction()).performScrollToIndex(1)
        compose.waitUntil(10_000) {compose.onAllNodes(hasText("2 of 3",substring=true)).fetchSemanticsNodes().isNotEmpty()}
        compose.onNode(hasScrollToIndexAction()).performScrollToNode(hasText("MS-first"))
        compose.onNodeWithText("MS-first").performClick()
        compose.waitUntil(10_000) {compose.onAllNodesWithText("Vehicle & Key").fetchSemanticsNodes().isNotEmpty()}
        Assert.assertEquals(0,exits)
        compose.onNodeWithTag("job-preparation-address").assertIsDisplayed()
        saveNativeQaImage(compose.onRoot(),"design-tablet-master-detail.png")
    }
    @Test fun ownerDashboardLoadsNativePeriodMetricsAndComparisons() {
        compose.setContent {MainspringTheme {MainspringAppShell("Native QA",server.url("/").toString(),{},setOf("auto_key","watch","shoe"))}}
        compose.onNodeWithTag("nav-today").performClick()
        compose.onNodeWithText("Needs your attention").assertExists()
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithTag("more-search").performTextInput("Report")
        compose.onNodeWithText("Reports").performClick()
        compose.onNodeWithTag("period-report-list").performScrollToNode(hasText("Revenue comparison"))
        compose.onNodeWithText("Revenue comparison").assertIsDisplayed()
        saveNativeQaImage(compose.onRoot(),"design-owner-dashboard.png")
    }
    @Test fun quickEnRouteActionRequiresConfirmationAndUsesJobVersion() {
        compose.setContent {MainspringTheme {AutoKeyJobDetailScreen("first",server.url("/").toString(),{},{},{},{},initialStatus="en_route")}}
        compose.waitUntil(10_000) {compose.onAllNodesWithText("Confirm En Route").fetchSemanticsNodes().isNotEmpty()}
        Assert.assertEquals(0,writes.get())
        compose.onNodeWithText("Confirm En Route").performClick()
        compose.waitUntil(10_000) {status=="en_route"}
        Assert.assertEquals(1,writes.get())
    }
    @Test fun reopeningQuoteComposerKeepsWorkAfterAnEarlierQuoteWasSaved() {
        val shown = androidx.compose.runtime.mutableStateOf(true)
        compose.setContent {MainspringTheme {if(shown.value) androidx.compose.foundation.layout.Column {QuoteComposer("reopen-quote",false,true,false,resetVersion="saved-quote",onSave={_,_,_->})}}}
        compose.onNodeWithText("Description").performTextInput("Retained replacement key")
        compose.runOnIdle {shown.value=false};compose.waitForIdle();compose.runOnIdle {shown.value=true}
        compose.onNodeWithText("Description").assertTextContains("Retained replacement key")
    }
    @Test fun plannerMoveThenSlotRequiresAConfirmedVersionedBookingUpdate() {
        compose.setContent {MainspringTheme {MobileWorkBoardScreen(server.url("/").toString(),{},{},{},{})}}
        compose.onNodeWithText("Planner").performClick()
        compose.waitUntil(10_000) {compose.onAllNodesWithTag("planner-move-first").fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithTag("planner-move-first").performSemanticsAction(SemanticsActions.OnClick) {it()}
        val day=LocalDate.now(ZoneId.of("Australia/Sydney"))
        compose.onNodeWithTag("planner-slot-$day-11-0").performSemanticsAction(SemanticsActions.OnClick) {it()}
        Assert.assertEquals(0,writes.get())
        compose.onNodeWithText("Confirm move").performClick()
        compose.waitUntil(10_000) {writes.get()==1}
        Assert.assertEquals("${day}T11:00+11:00",com.google.gson.JsonParser.parseString(patch).asJsonObject["scheduled_at"].asString)
    }

    @Test fun fieldJourneyConfirmsTravelArrivalCompletionAndPaymentInOneJob() {
        financeJourney=true
        compose.setContent {MainspringTheme {AutoKeyJobDetailScreen("first",server.url("/").toString(),{},{},{},{})}}
        compose.waitUntil(10_000) {compose.onAllNodes(hasTestTag("job-next-action") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        saveNativeQaImage(compose.onRoot(),"polish-job-booked.png")
        compose.onNodeWithTag("job-next-action").performClick()
        Assert.assertEquals(0,writes.get())
        compose.onNodeWithText("Confirm en route").performClick()
        compose.waitUntil(10_000) {status=="en_route"}
        compose.onNodeWithTag("job-next-action").performClick()
        compose.onNodeWithText("Confirm on site").performClick()
        compose.waitUntil(10_000) {status=="on_site"}
        saveNativeQaImage(compose.onRoot(),"polish-job-on-site.png")
        compose.onNodeWithText("Finish work").performClick()
        Assert.assertEquals(2,writes.get())
        compose.onNodeWithText("Confirm completion").performClick()
        compose.waitUntil(10_000) {compose.onAllNodesWithText("Payment to record",ignoreCase=true).fetchSemanticsNodes().isNotEmpty()}
        saveNativeQaImage(compose.onRoot(),"polish-payment-due.png")
        compose.onNodeWithText("Record payment",substring=false).performScrollTo().performClick()
        saveNativeQaImage(compose.onNodeWithTag("payment-sheet"),"polish-payment-sheet.png")
        compose.onNode(hasText("Record payment",substring=false) and hasClickAction() and hasAnyAncestor(hasTestTag("payment-sheet"))).performClick()
        compose.waitUntil(10_000) {invoicePaid && compose.onAllNodesWithText("All settled").fetchSemanticsNodes().isNotEmpty()}
        Assert.assertEquals(4,writes.get())
        saveNativeQaImage(compose.onRoot(),"polish-job-paid.png")
        compose.onNodeWithText("Back to job overview").performScrollTo().performClick()
        compose.onNodeWithTag("job-next-action").assertTextContains("View documents")
    }
    @Test fun interruptedRefreshShowsSavedJobAndBlocksStatusWritesUntilOnline() {
        val first=AutoKeyJobDetailViewModel("first",server.url("/").toString())
        compose.waitUntil(10_000) {!first.state.value.loading}
        disconnected=true
        val restored=AutoKeyJobDetailViewModel("first",server.url("/").toString())
        compose.waitUntil(10_000) {!restored.state.value.loading}
        Assert.assertEquals("first",restored.state.value.job?.id)
        Assert.assertTrue(restored.state.value.offlineSnapshot)
        restored.setStatus("en_route");Assert.assertEquals(0,writes.get())
        compose.setContent {MainspringTheme {AutoKeyJobDetailScreen("first",server.url("/").toString(),{},{},{},{},vm=restored)}}
        compose.onNodeWithText("Saved copy · reconnect to update").assertExists()
        compose.onNodeWithTag("job-next-action").assertIsNotEnabled()
        saveNativeQaImage(compose.onRoot(),"polish-offline-job.png")
        disconnected=false;restored.load()
        compose.waitUntil(10_000) {!restored.state.value.loading}
        Assert.assertFalse(restored.state.value.offlineSnapshot)
        compose.onNodeWithTag("job-next-action").assertIsEnabled()
    }
    @Test fun offlineTodayRestoresOnlyTodaysScopedSchedule() {
        val first=TodayViewModel();compose.waitUntil(10_000) {!first.state.value.loading}
        disconnected=true
        val restored=TodayViewModel();compose.waitUntil(10_000) {!restored.state.value.loading}
        Assert.assertTrue(restored.state.value.offlineSnapshot)
        Assert.assertEquals(listOf("first","second","third"),restored.state.value.jobs.map {it.id})
        TokenStore.setDraftScope("different-shop","design-user")
        val other=TodayViewModel();compose.waitUntil(10_000) {!other.state.value.loading}
        Assert.assertTrue(other.state.value.jobs.isEmpty())
    }

    @Test fun lostPaymentResponseSurvivesRecreationAndRequiresReviewBeforeRetry() {
        financeJourney=true;status="work_completed";lostPaymentResponse=true
        val first=MobileFinanceViewModel("first");compose.waitUntil(10_000) {!first.state.value.loading}
        first.markPaid("invoice-one","card");compose.waitUntil(10_000) {!first.state.value.busy}
        Assert.assertEquals("invoice-one",first.state.value.paymentReviewId)
        val restored=MobileFinanceViewModel("first");compose.waitUntil(10_000) {!restored.state.value.loading}
        Assert.assertEquals("paid",restored.state.value.invoices.single().status)
        restored.markPaid("invoice-one","card");Assert.assertEquals(1,writes.get())
        restored.checkedPayment();restored.markPaid("invoice-one","card")
        Assert.assertNull(restored.state.value.paymentReviewId);Assert.assertEquals(1,writes.get())
    }
    @Test fun jobNextActionRemainsVisibleWithLargeText() {
        compose.setContent {
            val density=androidx.compose.ui.platform.LocalDensity.current
            androidx.compose.runtime.CompositionLocalProvider(androidx.compose.ui.platform.LocalDensity provides androidx.compose.ui.unit.Density(density.density,1.5f)) {
                MainspringTheme {AutoKeyJobDetailScreen("first",server.url("/").toString(),{},{},{},{})}
            }
        }
        compose.waitUntil(10_000) {compose.onAllNodes(hasTestTag("job-next-action") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithTag("job-next-action").assertIsDisplayed()
        saveNativeQaImage(compose.onRoot(),"polish-large-text.png")
    }

    @Test fun quoteSheetKeepsTotalAndSaveVisibleAndRestoresUnfinishedWork() {
        compose.setContent {MainspringTheme {MobileFinanceScreen("first",{})}}
        compose.waitUntil(10_000) {compose.onAllNodes(hasText("Create quote") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Create quote").performClick()
        compose.onNodeWithText("Save draft quote").assertIsDisplayed().assertIsNotEnabled()
        compose.onNodeWithText("Description").performTextInput("Replacement key")
        compose.onNodeWithText("Unit price ($)").performTextInput("275")
        compose.onNodeWithText("Save draft quote").assertIsDisplayed().assertIsEnabled()
        compose.onNodeWithText("275.00 AUD").assertIsDisplayed()
        saveNativeQaImage(compose.onNodeWithTag("quote-editor"),"polish-quote-total.png")
        compose.onNodeWithText("Close").performClick()
        compose.onNodeWithText("Create quote").performClick()
        compose.onNodeWithText("Description").assertTextContains("Replacement key")
        compose.onNodeWithText("275.00 AUD").assertIsDisplayed()
    }
    @Test fun landscapeJobKeepsBodyAndNextActionVisible() {
        Assume.assumeTrue("Requires the isolated landscape viewport",InstrumentationRegistry.getInstrumentation().targetContext.resources.configuration.screenHeightDp<540)
        compose.setContent {MainspringTheme {AutoKeyJobDetailScreen("first",server.url("/").toString(),{},{},{},{})}}
        compose.waitUntil(10_000) {compose.onAllNodes(hasTestTag("job-next-action") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithTag("job-preparation-address").assertIsDisplayed()
        compose.onNodeWithTag("job-next-action").assertIsDisplayed()
        saveNativeQaImage(compose.onRoot(),"polish-landscape.png")
    }

    @Test fun switchingJobsDoesNotCarryCompletionNotesToAnotherCustomer() {
        status="on_site"
        val selected=androidx.compose.runtime.mutableStateOf("first")
        compose.setContent {MainspringTheme {AutoKeyJobDetailScreen(selected.value,server.url("/").toString(),{},{},{},{})}}
        compose.waitUntil(10_000) {compose.onAllNodes(hasText("Finish work") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Finish work").performClick()
        compose.onNodeWithText("Completion note (optional)").performTextInput("First job completion note")
        compose.onNodeWithText("Cancel").performClick()
        compose.runOnIdle {selected.value="second"}
        compose.waitUntil(10_000) {compose.onAllNodesWithText("MS-second").fetchSemanticsNodes().isNotEmpty() && compose.onAllNodes(hasText("Finish work") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Finish work").performClick()
        compose.onNodeWithText("First job completion note").assertDoesNotExist()
        Assert.assertEquals(0,writes.get())
    }

    @Test fun compactTodayShowsLaterTimesAndOpensTheTappedJob() {
        val vm=TodayViewModel();compose.waitUntil(10_000) {!vm.state.value.loading}
        var opened=""
        compose.setContent {MainspringTheme {TodayScreen({opened=it},{},{},vm,onEnRoute={})}}
        compose.onNodeWithText("13:00").assertIsDisplayed()
        compose.onNodeWithText("15:00").assertIsDisplayed()
        compose.onNodeWithTag("today-row-third").performClick()
        Assert.assertEquals("third",opened)
        saveNativeQaImage(compose.onRoot(),"aligned-today.png")
    }
    @Test fun overviewKeepsNotesVisibleAndRevealsCompleteBookingDetailsOnRequest() {
        compose.setContent {MainspringTheme {AutoKeyJobDetailScreen("first",server.url("/").toString(),{},{},{},{})}}
        compose.waitUntil(10_000) {compose.onAllNodes(hasTestTag("job-next-action") and isEnabled()).fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithText("Avery Technician").assertDoesNotExist()
        compose.onNodeWithText("Keys locked in tray.").assertExists()
        saveNativeQaImage(compose.onRoot(),"aligned-overview.png")
        compose.onNodeWithText("Customer & booking details").performScrollTo().performClick()
        compose.onNodeWithText("Avery Technician").assertExists()
        compose.onNodeWithText("Hide customer & booking details").performScrollTo().performClick()
        compose.onNodeWithText("Avery Technician").assertDoesNotExist()
    }

    @Test fun workspaceNavigationKeepsTodaySelectedAndReturnsFromMore() {
        compose.setContent {MainspringTheme {MainspringAppShell("Native QA",server.url("/").toString(),{},setOf("auto_key"))}}
        compose.waitUntil(10_000) {compose.onAllNodesWithText("Needs your attention").fetchSemanticsNodes().isNotEmpty()}
        compose.onNodeWithTag("nav-today").assertIsSelected()
        saveNativeQaImage(compose.onRoot(),"aligned-shell.png")
        compose.onNodeWithTag("nav-more").performClick()
        compose.onNodeWithTag("nav-more").assertIsSelected()
        compose.onNodeWithTag("nav-today").performClick()
        compose.onNodeWithTag("nav-today").assertIsSelected()
        compose.onNodeWithText("Needs your attention").assertExists()
    }
    @Test fun largeTextTodayKeepsDetailsAndScheduleReachable() {
        val vm=TodayViewModel();compose.waitUntil(10_000) {!vm.state.value.loading}
        var opened=""
        compose.setContent {
            val density=androidx.compose.ui.platform.LocalDensity.current
            androidx.compose.runtime.CompositionLocalProvider(androidx.compose.ui.platform.LocalDensity provides androidx.compose.ui.unit.Density(density.density,1.5f)) {
                MainspringTheme {TodayScreen({opened=it},{},{},vm,onEnRoute={})}
            }
        }
        compose.onNodeWithText("View details").performScrollTo().performClick()
        Assert.assertEquals("first",opened)
        compose.onNodeWithTag("today-list").performScrollToNode(hasTestTag("today-row-third"))
        compose.onNodeWithTag("today-row-third").performClick()
        Assert.assertEquals("third",opened)
        saveNativeQaImage(compose.onRoot(),"aligned-today-large-text.png")
    }

}
