package au.mainspring.nativeapp
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.InvoiceDetailScreen
import au.mainspring.nativeapp.ui.screens.MessageThreadScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.atomic.AtomicInteger
class CommercialUiTest {
 @get:Rule val compose = createComposeRule()
 private lateinit var server: MockWebServer
 private val payments = AtomicInteger(); private val messages = AtomicInteger()
 private var failPayment = false; private var failMessage = false; private var paymentAmount = 0
 private var mobileQuoteBody = ""; private var mobileInvoiceStatus = "unpaid"
 private var mobilePatch = ""; private var expectedUpdated = ""
 private var assignedTech: String? = null
 private var counterPatch = ""; private var counterTitle = "Battery"; private var counterDeposit = 0
 private val mobileQuote = """{"id":"mobile-quote","status":"draft","subtotal_cents":1117,"tax_cents":112,"total_cents":1229,"currency":"AUD","line_items":[{"description":"New key","quantity":1,"unit_price_cents":1229}]}"""
 private fun mobileInvoice() = """{"id":"mobile-invoice","auto_key_quote_id":"mobile-quote","invoice_number":"MS-1","status":"$mobileInvoiceStatus","total_cents":1229,"currency":"AUD"}"""
 private val invoice = """{"id":"invoice-1","invoice_number":"INV-1","repair_job_id":"job-1","status":"unpaid","subtotal_cents":10000,"tax_cents":0,"total_cents":10000,"currency":"AUD","created_at":"2026-10-07T00:00:00Z"}"""
 @Before fun setup() {
  TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
  server = MockWebServer()
  server.dispatcher = object: Dispatcher() {
   override fun dispatch(request: RecordedRequest): MockResponse {
    val path = request.path.orEmpty().substringBefore('?')
    val body = when {
     path == "/v1/users" -> """[{"id":"tech-1","full_name":"Avery Technician","role":"tech","is_active":true}]"""
     path == "/v1/repair-jobs/job-1" -> {
      if(request.method == "PATCH") { counterPatch = request.body.readUtf8(); val fields = com.google.gson.JsonParser.parseString(counterPatch).asJsonObject; if(fields.has("deposit_cents")) counterDeposit = fields["deposit_cents"].asInt }
      """{"id":"job-1","job_number":"W001","title":"$counterTitle","priority":"normal","status":"working_on","deposit_cents":$counterDeposit,"parts_eta":"2026-10-09"}"""
     }
     path == "/v1/auto-key-jobs/job-1" -> {
      if(request.method == "PATCH") { mobilePatch = request.body.readUtf8(); expectedUpdated = request.getHeader("X-Expected-Updated-At").orEmpty() }
      """{"id":"job-1","title":"Replacement key","assigned_user_id":${assignedTech?.let { "\"$it\"" } ?: "null"},"updated_at":"2026-10-07T00:00:00Z","key_quantity":1,"programming_status":"pending","scheduled_at":"2026-10-09T09:30:00+11:00"}"""
     }
     path == "/v1/auto-key-jobs/page" -> """{"items":[],"total":0,"limit":50,"offset":0}"""
     path == "/v1/auto-key-jobs/job-1/quotes" && request.method == "POST" -> { mobileQuoteBody = request.body.readUtf8(); mobileQuote }
     path == "/v1/auto-key-jobs/job-1/quotes" -> if(mobileQuoteBody.isBlank()) "[]" else "[$mobileQuote]"
     path == "/v1/auto-key-jobs/job-1/invoices" -> "[${mobileInvoice()}]"
     path == "/v1/auto-key-jobs/job-1/invoices/from-quote/mobile-quote" -> return MockResponse().setResponseCode(409)
     path == "/v1/auto-key-jobs/invoices/mobile-invoice" -> { mobileInvoiceStatus = com.google.gson.JsonParser.parseString(request.body.readUtf8()).asJsonObject["status"].asString; mobileInvoice() }
     path == "/v1/invoices" -> """{"items":[$invoice],"total":1,"limit":100,"offset":0}"""
     path == "/v1/invoices/invoice-1" -> """{"invoice":$invoice,"payments":${if(paymentAmount == 0) "[]" else "[${payment()}]"}}"""
     path.endsWith("/line-items") -> "[]"
     path.endsWith("/payments") -> { payments.incrementAndGet(); if(failPayment) return MockResponse().setResponseCode(503)
      paymentAmount = com.google.gson.JsonParser.parseString(request.body.readUtf8()).asJsonObject["amount_cents"].asInt; payment() }
     path.endsWith("/messages") && request.method == "GET" -> "[]"
     path.endsWith("/messages") -> { messages.incrementAndGet(); if(failMessage) return MockResponse().setResponseCode(503)
      """{"id":"msg-1","direction":"outbound","body":"Your repair is ready","created_at":"2026-10-07T00:00:00Z"}""" }
     path.endsWith("/send") -> """{"invoice_id":"invoice-1","email_sent":false,"email_skipped_reason":"email_disabled"}"""
     else -> return MockResponse().setResponseCode(404)
    }; return MockResponse().setHeader("Content-Type", "application/json").setBody(body)
   }
  }
  server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("test-tenant", "test-user"); TokenStore.setSessionRole("manager")
 }
 private fun payment() = """{"id":"payment-1","invoice_id":"invoice-1","amount_cents":$paymentAmount,"currency":"AUD","status":"succeeded","provider":"manual"}"""
 @After fun cleanup() { TokenStore.clear(); server.shutdown() }
 @Test fun invoicePageContractLoadsCurrentBackendShape() {
  val vm = InvoicesViewModel(); compose.waitUntil(10_000) { !vm.state.value.loading }
  Assert.assertNull(vm.state.value.error); Assert.assertEquals("INV-1", vm.state.value.invoices.single().invoiceNumber); Assert.assertEquals(1, vm.state.value.total)
 }
 @Test fun paymentControlStoresExactCentsAndUpdatesRemaining() {
  val vm = InvoiceDetailViewModel("invoice-1")
  compose.setContent { MainspringTheme { InvoiceDetailScreen("invoice-1", {}, vm) } }
  compose.waitUntil(10_000) { vm.state.value.data != null }
  compose.onNodeWithText("Record payment").performClick(); compose.onNodeWithText("Amount").performTextInput("12.29"); compose.onNodeWithText("Save").performClick()
  compose.waitUntil(10_000) { vm.state.value.paymentInfo == "Payment recorded." && !vm.state.value.paymentBusy }
  Assert.assertEquals(1229, paymentAmount); Assert.assertEquals(1, payments.get())
  compose.onNodeWithText("Paid 12.29 AUD · Remaining 87.71 AUD").assertExists()
 }
 @Test fun unknownPaymentBlocksSubmissionAfterViewModelRecreation() {
  failPayment = true; val first = InvoiceDetailViewModel("invoice-1"); compose.waitUntil(10_000) { first.state.value.data != null }
  compose.runOnIdle { first.recordPayment(1229, null) }; compose.waitUntil(10_000) { first.state.value.paymentUnknown }
  val restored = InvoiceDetailViewModel("invoice-1"); compose.waitUntil(10_000) { restored.state.value.data != null }
  Assert.assertTrue(restored.state.value.paymentUnknown); compose.runOnIdle { restored.recordPayment(1229, null) }; Assert.assertEquals(1, payments.get())
 }
 @Test fun customerMessageSentFromNativeComposerClearsDraft() {
  val vm = MessageThreadViewModel("repair-jobs", "job-1")
  compose.setContent { MainspringTheme { MessageThreadScreen("repair-jobs", "job-1", {}, vm) } }
  compose.onNodeWithText("Message to customer").performTextInput("Your repair is ready"); compose.onNodeWithText("Send to customer").performClick()
  compose.waitUntil(10_000) { vm.state.value.messages.isNotEmpty() }
  Assert.assertEquals(1, messages.get()); Assert.assertEquals("", TokenStore.loadMessageDraft("repair-jobs/job-1")); compose.onNodeWithText("Your repair is ready").assertExists()
 }
 @Test fun unknownMessageSurvivesRestartAndRequiresFreshHistory() {
  failMessage = true; val first = MessageThreadViewModel("auto-key-jobs", "job-1")
  compose.runOnIdle { first.setDraft("Your repair is ready"); first.send() }; compose.waitUntil(10_000) { first.state.value.uncertain }
  val restored = MessageThreadViewModel("auto-key-jobs", "job-1"); Assert.assertTrue(restored.state.value.uncertain)
  compose.runOnIdle { restored.acknowledgeHistory(); restored.send() }; Assert.assertTrue(restored.state.value.uncertain); Assert.assertEquals(1, messages.get())
  compose.runOnIdle { restored.refresh() }; compose.waitUntil(10_000) { restored.state.value.historyChecked }; compose.runOnIdle { restored.acknowledgeHistory() }; Assert.assertFalse(restored.state.value.uncertain)
 }
 @Test fun disabledInvoiceEmailShowsReasonWithoutClaimingDelivery() {
  val vm = InvoiceDetailViewModel("invoice-1"); compose.waitUntil(10_000) { vm.state.value.data != null }; compose.runOnIdle { vm.sendInvoice() }
  compose.waitUntil(10_000) { vm.state.value.sendInfo != null }; Assert.assertEquals("Email notifications are disabled for this shop.", vm.state.value.sendInfo)
 }
 @Test fun mobileQuoteUsesExactPriceAndServerGstTotals() {
  val vm = MobileFinanceViewModel("job-1"); compose.waitUntil(10_000) { !vm.state.value.loading }
  compose.runOnIdle { vm.createQuote(listOf(au.mainspring.nativeapp.api.MobileQuoteLine("New key", 1.0, 1229)), true, true) }
  compose.waitUntil(10_000) { vm.state.value.quotes.isNotEmpty() && !vm.state.value.busy }
  val body = com.google.gson.JsonParser.parseString(mobileQuoteBody).asJsonObject
  Assert.assertTrue(body["gst_inclusive"].asBoolean); Assert.assertEquals(1229, body["line_items"].asJsonArray[0].asJsonObject["unit_price_cents"].asInt)
  Assert.assertEquals(112, vm.state.value.quotes.single().tax)
 }
 @Test fun existingMobileInvoiceIsRecoveredAndCanBeMarkedPaid() {
  val vm = MobileFinanceViewModel("job-1"); compose.waitUntil(10_000) { !vm.state.value.loading }
  compose.runOnIdle { vm.createInvoice("mobile-quote") }
  compose.waitUntil(10_000) { !vm.state.value.busy && vm.state.value.info != null }
  Assert.assertNull(vm.state.value.error); Assert.assertEquals(1, vm.state.value.invoices.size)
  compose.runOnIdle { vm.markPaid("mobile-invoice", "card") }; compose.waitUntil(10_000) { vm.state.value.invoices.single().status == "paid" }
 }
 @Test fun mobileEditingRestoresDraftAndSendsExplicitBookingClearWithVersion() {
  val first = MobileEditorViewModel("job-1"); compose.waitUntil(10_000) { !first.state.value.loading }
  compose.runOnIdle { first.set("tech_notes", "Bring replacement blade"); first.set("scheduled_at", "") }
  val restored = MobileEditorViewModel("job-1"); compose.waitUntil(10_000) { !restored.state.value.loading }
  Assert.assertEquals("Bring replacement blade", restored.state.value.fields["tech_notes"])
  compose.runOnIdle { restored.save() }; compose.waitUntil(10_000) { restored.state.value.saved }
  val body = com.google.gson.JsonParser.parseString(mobilePatch).asJsonObject
  Assert.assertTrue(body["scheduled_at"].isJsonNull); Assert.assertFalse(body.has("title"))
  Assert.assertEquals("2026-10-07T00:00:00Z", expectedUpdated)
 }
 @Test fun nativeTechnicianPickerSendsSelectedTeamMemberAndOriginalVersion() {
  compose.setContent { MainspringTheme { au.mainspring.nativeapp.ui.screens.MobileEditorScreen("job-1", {}) } }
  compose.waitUntil(10_000) { compose.onAllNodes(hasText("Change technician") and isEnabled()).fetchSemanticsNodes().isNotEmpty() }
  compose.onNodeWithText("Change technician").performScrollTo().performClick()
  compose.waitUntil(10_000) {compose.onAllNodesWithText("Avery Technician").fetchSemanticsNodes().isNotEmpty()}
  compose.onNodeWithText("Avery Technician").performClick()
  compose.onNodeWithText("Save job changes").performScrollTo().performClick()
  compose.waitUntil(10_000) { mobilePatch.isNotBlank() }
  val body = com.google.gson.JsonParser.parseString(mobilePatch).asJsonObject
  Assert.assertEquals("tech-1", body["assigned_user_id"].asString)
  Assert.assertEquals(1, body.size()); Assert.assertEquals("2026-10-07T00:00:00Z", expectedUpdated)
 }
 @Test fun unassignmentUsesExplicitNullWithoutChangingOtherJobFields() {
  assignedTech = "tech-1"
  val vm = MobileEditorViewModel("job-1"); compose.waitUntil(10_000) { !vm.state.value.loading }
  vm.set("assigned_user_id", ""); vm.save(); compose.waitUntil(10_000) { vm.state.value.saved }
  val body = com.google.gson.JsonParser.parseString(mobilePatch).asJsonObject
  Assert.assertTrue(body["assigned_user_id"].isJsonNull); Assert.assertEquals(1, body.size())
 }
 @Test fun counterEditorPreservesExactDepositAndClearsPartsEtaExplicitly() {
  val vm = CounterEditorViewModel("repair-jobs", "job-1"); compose.waitUntil(10_000) { !vm.state.value.loading }
  compose.runOnIdle { vm.set("deposit_cents", "12.29"); vm.set("parts_eta", ""); vm.save() }
  compose.waitUntil(10_000) { vm.state.value.saved || vm.state.value.error != null }
  Assert.assertNull(vm.state.value.error)
  val body = com.google.gson.JsonParser.parseString(counterPatch).asJsonObject
  Assert.assertEquals(1229, body["deposit_cents"].asInt); Assert.assertTrue(body["parts_eta"].isJsonNull); Assert.assertFalse(body.has("title"))
 }
 @Test fun counterEditorBlocksOverwritingAnotherOperatorsChangedJob() {
  val vm = CounterEditorViewModel("repair-jobs", "job-1"); compose.waitUntil(10_000) { !vm.state.value.loading }
  counterTitle = "Updated by another operator"
  compose.runOnIdle { vm.set("description", "My earlier draft"); vm.save() }
  compose.waitUntil(10_000) { vm.state.value.conflict }
  Assert.assertEquals("", counterPatch); Assert.assertEquals("My earlier draft", vm.state.value.fields["description"])
 }
 @Test fun invoiceSupportsDarkModeAndLargerText() {
  val vm = InvoiceDetailViewModel("invoice-1")
  compose.setContent { val density = androidx.compose.ui.platform.LocalDensity.current
   androidx.compose.runtime.CompositionLocalProvider(androidx.compose.ui.platform.LocalDensity provides androidx.compose.ui.unit.Density(density.density, 1.3f)) {
    MainspringTheme(darkTheme = true) { InvoiceDetailScreen("invoice-1", {}, vm) }
   }
  }
  compose.waitUntil(10_000) { vm.state.value.data != null }
  compose.onNodeWithText("Record payment").performScrollTo().assertIsDisplayed()
  saveNativeQaImage(compose.onRoot(), "invoice-large-font-dark.png")
 }
}
