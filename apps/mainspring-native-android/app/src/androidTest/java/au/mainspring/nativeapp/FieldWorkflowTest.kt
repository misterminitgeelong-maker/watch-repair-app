package au.mainspring.nativeapp
import androidx.compose.ui.test.*
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.ToolkitScreen
import au.mainspring.nativeapp.ui.screens.BookingRequestsScreen
import au.mainspring.nativeapp.ui.screens.CustomerEditorScreen
import au.mainspring.nativeapp.ui.screens.WorkLogsScreen
import au.mainspring.nativeapp.ui.screens.QuoteComposer
import au.mainspring.nativeapp.ui.screens.PricingPicker
import au.mainspring.nativeapp.ui.screens.CounterSaleScreen
import okhttp3.mockwebserver.*
import com.google.gson.JsonParser
import org.junit.*
class FieldWorkflowTest {
 @get:Rule val compose = createComposeRule()
 private lateinit var server: MockWebServer
 private var recommendBody = ""; private var advanceBody = ""
 private var bookingBody = ""; private var failBooking = false; private var customerWrites = 0
 private var workLogBody = ""
 private var saleQuotes = 0; private var saleInvoices = 0; private var saleCompletions = 0; private var saleQuoteBody = ""
 @Before fun setup() {
  TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
  server = MockWebServer(); server.dispatcher = object: Dispatcher() {
   override fun dispatch(request: RecordedRequest): MockResponse {
    val path = request.path.orEmpty().substringBefore('?')
    val body = when {
     path == "/v1/customer-accounts" -> "[]"
     path == "/v1/auto-key-jobs" -> """{"id":"sale-job","title":"POS sale","job_number":"M001"}"""
     path == "/v1/auto-key-jobs/sale-job/quotes" -> { saleQuotes++; saleQuoteBody = request.body.readUtf8(); """{"id":"sale-quote","status":"draft","subtotal_cents":16364,"tax_cents":1636,"total_cents":18000,"currency":"AUD","line_items":[]}""" }
     path == "/v1/auto-key-jobs/sale-job/invoices/from-quote/sale-quote" -> { saleInvoices++; """{"id":"sale-invoice","invoice_number":"I001","status":"unpaid","total_cents":18000,"currency":"AUD"}""" }
     path == "/v1/auto-key-jobs/sale-job/status" -> { saleCompletions++; """{"id":"sale-job","status":"work_completed"}""" }
     path == "/v1/mobile-services-pricing/meta" -> """{"enabled_categories":["vehicle_key","general_service"]}"""
     path == "/v1/mobile-services-pricing/oem-makes" -> "[\"Toyota\"]"
     path == "/v1/mobile-services-pricing/oem-keys" -> """[{"id":"price-1","make":"Toyota","model_variant":"Corolla","job_type":"Add key","retail_price":128.99,"callout_inclusive":true}]"""
     path == "/v1/mobile-services-pricing/services" -> "[]"
     path == "/v1/work-logs" && request.method == "GET" -> "[]"
     path == "/v1/work-logs" -> { workLogBody = request.body.readUtf8(); """{"id":"work-1","note":"Replaced battery and tested seal","minutes_spent":15,"created_at":"2026-10-07T00:00:00Z"}""" }
     path == "/v1/shop-mobile-bookings/operators" -> "[]"
     path == "/v1/shop-mobile-bookings" && request.method == "GET" -> """{"items":[],"total":0}"""
     path == "/v1/shop-mobile-bookings" -> {
      bookingBody = request.body.readUtf8(); if(failBooking) return MockResponse().setResponseCode(503)
      """{"id":"booking-1","status":"pending","customer_name":"Avery","requesting_tenant_id":"tenant","target_operator_tenant_id":"operator-1","requesting_shop_name":"Our shop","target_operator_name":"Mobile team","job_address":"10 Test Street"}"""
     }
     path == "/v1/customers" && request.method == "GET" -> "[]"
     path == "/v1/customers" -> { customerWrites++; """{"id":"customer-1","full_name":"Avery","tenant_id":"tenant","created_at":"2026-10-07T00:00:00Z"}""" }
     path == "/v1/toolkit/catalog" -> """{"title":"Toolkit","groups":[{"id":"bench","label":"Bench tools","tools":[{"key":"programmer","name":"Key programmer"}]}],"scenarios":[{"id":"key","label":"Replacement key"}]}"""
     path == "/v1/toolkit/my-selection" -> if(request.method == "PUT") request.body.readUtf8() else """{"tool_keys":[]}"""
     path == "/v1/toolkit/recommend" -> { recommendBody = request.body.readUtf8(); """{"label":"Replacement key","ready_for_required":true,"missing_required":[],"missing_nice_to_have":[]}""" }
     path == "/v1/prospects/categories" -> """{"categories":[{"key":"garage","label":"Garages"}]}"""
     path == "/v1/prospect-leads" -> """[{"id":"lead-1","name":"Avery Garage","status":"visited"}]"""
     path == "/v1/prospect-leads/lead-1/advance" -> { advanceBody = request.body.readUtf8(); """{"id":"lead-1","name":"Avery Garage","status":"onboarded","customer_account_id":"account-1","contact_name":"Avery New"}""" }
     else -> return MockResponse().setResponseCode(404)
    }; return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
   }
  }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant", "user"); TokenStore.setSessionRole("manager")
 }
 @After fun cleanup() { TokenStore.clear(); server.shutdown() }
 @Test fun toolkitDraftReadinessUsesVisibleSelectionAndPersistsUntilSaved() {
  val vm = ToolkitViewModel(); compose.setContent { MainspringTheme { ToolkitScreen({}, vm) } }
  compose.waitUntil(10_000) { !vm.state.value.loading }
  compose.onAllNodes(isToggleable()).onFirst().performClick()
  compose.onNodeWithText("1 tools selected · unsaved draft").assertExists()
  compose.onNodeWithText("Replacement key").performScrollTo().performClick()
  compose.waitUntil(10_000) { vm.state.value.readiness != null }
  Assert.assertEquals("programmer", JsonParser.parseString(recommendBody).asJsonObject["tool_keys"].asJsonArray[0].asString)
  val restored = ToolkitViewModel(); compose.waitUntil(10_000) { !restored.state.value.loading }
  Assert.assertTrue("programmer" in restored.state.value.selected); Assert.assertTrue(restored.state.value.saved.isEmpty())
  compose.onNodeWithText("Save selection").performClick()
  compose.waitUntil(10_000) { vm.state.value.saved.contains("programmer") }
  Assert.assertEquals("", TokenStore.loadMessageDraft("toolkit"))
 }
 @Test fun prospectAdvanceSavesVisibleContactsAndExplicitVisitClearAtomically() {
  val vm = ProspectViewModel(); compose.waitUntil(10_000) { !vm.state.value.loading }
  compose.runOnIdle { vm.update("lead-1", "Avery New", "avery@example.test", "Ready for account", "", true, {}) }
  compose.waitUntil(10_000) { vm.state.value.leads.single().accountId != null }
  val body = JsonParser.parseString(advanceBody).asJsonObject
  Assert.assertEquals("Avery New", body["contact_name"].asString); Assert.assertTrue(body["visit_scheduled_at"].isJsonNull)
  Assert.assertEquals("", TokenStore.loadMessageDraft("prospect-advance"))
 }
 @Test fun bookingRequestControlRequiresConfirmationAndUsesTimezone() {
  TokenStore.setCalendarTimezone("Australia/Sydney")
  val vm = BookingViewModel(); compose.waitUntil(10_000) { !vm.state.value.loading }
  compose.runOnIdle { vm.set("customer_name", "Avery"); vm.set("suburb", "Geelong"); vm.set("state_code", "VIC"); vm.set("job_address", "10 Test Street"); vm.set("preferred_scheduled_at", "09/10/2026 09:30") }
  compose.setContent { MainspringTheme { BookingRequestsScreen(true, {}, {}, vm) } }
  compose.onNodeWithText("New request").performClick()
  compose.onNodeWithText("Review and send request").performScrollTo().performClick()
  Assert.assertEquals("", bookingBody)
  compose.onNodeWithText("Confirm").performClick()
  compose.waitUntil(10_000) { vm.state.value.rows.isNotEmpty() }
  val json = JsonParser.parseString(bookingBody).asJsonObject
  Assert.assertEquals("2026-10-09T09:30+11:00", json["preferred_scheduled_at"].asString)
  saveNativeQaImage(compose.onRoot(), "booking-request-created.png")
 }
 @Test fun unknownBookingRequestRestoresDraftAndBlocksBlindRetry() {
  failBooking = true; val vm = BookingViewModel(); compose.waitUntil(10_000) { !vm.state.value.loading }
  compose.runOnIdle { vm.set("customer_name", "Avery"); vm.set("suburb", "Geelong"); vm.set("state_code", "VIC"); vm.set("job_address", "10 Test Street"); vm.create {} }
  compose.waitUntil(10_000) { vm.state.value.uncertain }
  val restored = BookingViewModel(); compose.waitUntil(10_000) { !restored.state.value.loading }
  Assert.assertTrue(restored.state.value.uncertain); Assert.assertEquals("Avery", restored.state.value.fields["customer_name"])
 }
 @Test fun standaloneCustomerControlCreatesOnlyOneRecord() {
  compose.setContent { MainspringTheme { CustomerEditorScreen("", {}) } }
  compose.onNodeWithText("Name *").performTextInput("Avery")
  compose.onNodeWithText("Create customer").performScrollTo().performClick()
  compose.waitUntil(10_000) { compose.onAllNodesWithText("Customer created").fetchSemanticsNodes().isNotEmpty() }
  compose.onNodeWithText("Create customer").assertIsNotEnabled(); Assert.assertEquals(1, customerWrites)
 }
 @Test fun nativeWorkLogRecordsNoteAndMinutesForTheCorrectJob() {
  val vm = WorkLogsViewModel("job-1"); compose.setContent { MainspringTheme { WorkLogsScreen("job-1", {}, vm) } }
  compose.waitUntil(10_000) { !vm.state.value.loading }
  compose.onNodeWithText("Work completed").performTextInput("Replaced battery and tested seal")
  compose.onNodeWithText("Minutes spent").performTextInput("15")
  compose.onNodeWithText("Save work log").performClick()
  compose.waitUntil(10_000) { vm.state.value.rows.isNotEmpty() }
  val body = JsonParser.parseString(workLogBody).asJsonObject
  Assert.assertEquals("job-1", body["repair_job_id"].asString); Assert.assertEquals(15, body["minutes_spent"].asInt)
  compose.onNodeWithText("15 minutes logged").assertExists()
 }
 @Test fun quoteComposerAppliesDiscountAndRestoresEditableDraft() {
  var result: List<au.mainspring.nativeapp.api.MobileQuoteLine>? = null
  compose.setContent { MainspringTheme { androidx.compose.foundation.layout.Column(androidx.compose.ui.Modifier.then(androidx.compose.ui.Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()))) {
   QuoteComposer("composer-test", false, true, false, onSave = { lines, _, _ -> result = lines })
  } } }
  compose.onNodeWithText("Description").performTextInput("Mobile key")
  compose.onNodeWithText("Unit price ($)").performTextInput("100")
  compose.onNodeWithText("% discount").performScrollTo().performClick()
  compose.onNodeWithText("Discount percentage").performTextInput("10")
  compose.onNodeWithText("Save draft quote").performScrollTo().performClick()
  Assert.assertEquals(9000, result!!.single().unitCents)
  val saved = com.google.gson.Gson().fromJson(TokenStore.loadMessageDraft("composer-test"), QuoteComposerDraft::class.java)
  Assert.assertEquals("10", saved.lines.single().discount)
 }
 @Test fun pricingPickerUsesEnabledCatalogueAndPreservesExactPrice() {
  var selected: au.mainspring.nativeapp.api.PricingRow? = null
  compose.setContent { MainspringTheme { PricingPicker({}, { selected = it }) } }
  compose.waitUntil(10_000) { compose.onAllNodesWithText("Toyota · Corolla · Add key").fetchSemanticsNodes().isNotEmpty() }
  compose.onNodeWithText("Garage doors").assertDoesNotExist()
  compose.onNodeWithText("Toyota · Corolla · Add key").performClick()
  Assert.assertEquals("128.99", selected!!.price!!.toPlainString())
 }
 @Test fun nativeCounterSaleCreatesQuoteInvoiceAndCompletesOnlyAfterConfirmation() {
  val vm = CounterSaleViewModel()
  compose.setContent { MainspringTheme { CounterSaleScreen({}, { _,_ -> },vm) } }
  compose.waitUntil(10_000) { !vm.state.value.customerLoading }
  compose.onNodeWithText("New customer").performClick()
  compose.onNodeWithText("Customer name *").performScrollTo().performTextInput("Avery")
  compose.onNodeWithText("Description").performScrollTo().performTextInput("Mobile key")
  compose.onNodeWithText("Quantity").performScrollTo().performTextClearance(); compose.onNodeWithText("Quantity").performTextInput("2")
  compose.onNodeWithText("Unit price ($)").performScrollTo().performTextInput("100")
  compose.onNodeWithText("% discount").performScrollTo().performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.OnClick) { it() }
  compose.onNodeWithText("Discount percentage").performScrollTo().performTextInput("10")
  compose.onNodeWithText("Review counter sale").performScrollTo().performClick()
  Assert.assertEquals(0,saleQuotes)
  compose.onNodeWithText("Confirm checkout").performClick()
  compose.waitUntil(15_000) { vm.field("done") == "true" || (!vm.state.value.busy && vm.state.value.error != null) }
  Assert.assertNull(vm.state.value.error); Assert.assertEquals(1,saleQuotes); Assert.assertEquals(1,saleInvoices); Assert.assertEquals(1,saleCompletions)
  Assert.assertEquals(9000,JsonParser.parseString(saleQuoteBody).asJsonObject["line_items"].asJsonArray[0].asJsonObject["unit_price_cents"].asInt)
  compose.onNodeWithText("Sale and unpaid invoice created").assertExists()
  saveNativeQaImage(compose.onRoot(),"counter-sale-complete.png")
 }
}
