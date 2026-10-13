package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import kotlinx.coroutines.runBlocking
import org.junit.*

/** Opt-in integration check: only a disposable loopback server is accepted. */
class LocalBackendSmokeTest {
    @Test fun nativeClientRoundTripsThroughActualAuthJobsFinanceReportsAndStock() = runBlocking {
        val arguments = InstrumentationRegistry.getArguments()
        val base = arguments.getString("localApiBaseUrl")
        Assume.assumeTrue("Requires the isolated qa/local_backend.py server", base != null)
        require(base == "http://127.0.0.1:8716/") { "This test must never target a production server." }
        val slug = arguments.getString("localTenantSlug")!!
        val email = arguments.getString("localOwnerEmail")!!
        require(slug.startsWith("native-qa-") && email.endsWith("@native.example.test"))
        val demoOnly = arguments.getString("localDemoOnly") == "true"
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        try {
            TokenStore.saveApiBaseUrl(base)
            val token = ApiClient.api.login(LoginRequest(slug, email, "Native-local-test-only!"))
            TokenStore.saveTokens(token.accessToken, token.refreshToken)
            val api = ApiClient.api
            val session = api.session()
            Assert.assertEquals(slug, session.tenantSlug); Assert.assertEquals("owner", session.user.role)
            TokenStore.setDraftScope(session.tenantId, session.user.id); TokenStore.setSessionRole(session.user.role); TokenStore.setCalendarTimezone(session.calendarTimezone)
            TokenStore.setShopIdentity(session.currency,session.shopName,session.shopAbn,session.shopPhone,session.shopAddress)
            if(demoOnly) {
                // Opt-in fixture setup for a visible walkthrough, rather than a validation run.
                au.mainspring.nativeapp.ui.DesignPreferences.init(InstrumentationRegistry.getInstrumentation().targetContext)
                au.mainspring.nativeapp.ui.DesignPreferences.select(au.mainspring.nativeapp.ui.AppAppearance.WARM)
                au.mainspring.nativeapp.ui.DesignPreferences.fieldNavigation(true)
                val context = InstrumentationRegistry.getInstrumentation().targetContext
                context.startActivity(android.content.Intent(context, MainActivity::class.java).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
                return@runBlocking
            }
            Assert.assertEquals("AUD",session.currency)
            val tech=api.createTeamUser(JsonObject().apply {
                addProperty("email","tech-${java.util.UUID.randomUUID()}@native.example.test");addProperty("full_name","Native QA technician");addProperty("password","Native-test-account-only!");addProperty("role","tech")
                addProperty("mobile_commission_rules_json", "{\"enabled\":true,\"retainer_cents_per_period\":0,\"rates_bp\":{\"shop_referred\":3000,\"tech_sourced\":5000,\"minit_sourced\":4000}}")
            })
            Assert.assertEquals("tech",tech.role)
            Assert.assertEquals("Native QA technician updated",api.updateTeamUser(tech.id,JsonObject().apply {addProperty("full_name","Native QA technician updated")}).name)
            Assert.assertTrue(api.vehicleJobContext("Toyota","Hilux",2019,"All Keys Lost",null).has("known_issues"))
            val customer = api.createCustomer(CustomerCreate("Native integration QA", address = "10 Test Street", notes = "Disposable test record"))
            val changed = api.updateCustomerFields(customer.id, JsonObject().apply { add("address", JsonNull.INSTANCE) })
            Assert.assertNull(changed.address)
            Assert.assertTrue(api.listCustomers(q = "Native integration QA", limit = 200).any { it.id == customer.id })
            val watch = api.createWatch(WatchCreate(customer.id, "Test brand", "Test model", "QA-001", "Test condition", "quartz"))
            val repair = api.postRepairJob(RepairJobCreate(watch.id, title = "Native watch repair", status = "working_on"))
            Assert.assertEquals("completed", api.postRepairJobStatus(repair.id, RepairJobStatusUpdate("completed", "Local QA completed")).status)
            Assert.assertTrue(api.getRepairJobStatusHistory(repair.id).isNotEmpty())
            val mobile = api.createMobileJob(MobileJobCreate(customerId = customer.id, title = "Native mobile job", description = "Disposable key job", priority = "normal", status = "awaiting_quote",
                scheduledAt = "2026-10-09T09:30:00+11:00", address = "10 Test Street", jobType = "vehicle_key", make = "Test", model = "QA", year = 2020, plate = "QA000", vin = null,
                keyType = "spare", keyQuantity = 1, techNotes = null, deposit = 0))
            Assert.assertEquals(java.time.Instant.parse("2026-10-08T22:30:00Z"),bookingInstant(mobile.scheduledAt))
            val edited = api.updateMobileJob(mobile.id, JsonObject().apply { add("scheduled_at", JsonNull.INSTANCE); addProperty("title", "Edited native mobile job") }, mobile.updatedAt)
            Assert.assertNull(edited.scheduledAt)
            val moved=api.updateMobileJob(mobile.id,JsonObject().apply {addProperty("scheduled_at","2026-10-09T11:00:00+11:00");addProperty("assigned_user_id",tech.id)},edited.updatedAt)
            Assert.assertEquals(tech.id,moved.assignedUserId)
            Assert.assertEquals(java.time.Instant.parse("2026-10-09T00:00:00Z"),bookingInstant(moved.scheduledAt))
            val quote = api.createMobileQuote(mobile.id, MobileQuoteCreate(listOf(MobileQuoteLine("Test key", 2.0, 1234)), gst = true, inclusive = false))
            Assert.assertEquals(2468, quote.subtotal); Assert.assertTrue(quote.total > quote.subtotal)
            val invoice = api.createMobileInvoice(mobile.id, quote.id)
            Assert.assertEquals(quote.total, invoice.total); Assert.assertEquals(quote.currency, invoice.currency)
            Assert.assertEquals("paid", api.updateMobileInvoice(invoice.id, MobileInvoiceUpdate("paid", "cash")).status)
            val completed = api.postAutoKeyJobStatus(mobile.id, RepairJobStatusUpdate("work_completed"), moved.updatedAt)
            Assert.assertEquals("work_completed", completed.status)
            Assert.assertTrue(api.mobileCommission("2026-10-01","2026-10-31").has("technicians"))
            val report = api.periodReport("quarter", "2026-10-09")
            Assert.assertTrue(report.jobs >= 2)
            api.exportPeriodReport("quarter", "2026-10-09").use { Assert.assertTrue(it.string().contains("revenue_cents")) }
            val stock = api.stockItems(search = "NATIVE-QA-BAT").items.single()
            Assert.assertEquals(5.0, stock.quantity, 0.0)
        } finally { if(!demoOnly) TokenStore.clear() }
    }
}
