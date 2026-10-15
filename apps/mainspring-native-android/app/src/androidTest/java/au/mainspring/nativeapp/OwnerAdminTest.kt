package au.mainspring.nativeapp

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.TeamUser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

class OwnerAdminTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()
    private val bodies = ConcurrentLinkedQueue<String>()
    private val identity = """{"name":"Test Shop","abn":"12 345","shop_phone":"0400","shop_email":"a@b.co","region":"AU","default_currency":"AUD","timezone":"Australia/Melbourne"}"""
    private val prefs = """{"email_quote_approved":true,"email_invoice_paid":false,"email_sms_reply":false,"email_daily_digest":false,"email_weekly_sales_report":false,"email_monthly_sales_report":false}"""

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty()
                requests.add(request.method + " " + path)
                val json = { body: String -> MockResponse().setHeader("Content-Type", "application/json").setBody(body) }
                return when {
                    path.startsWith("/v1/settings/shop-identity") && request.method == "PATCH" -> { bodies.add(request.body.readUtf8()); json(identity.replace("0400", "0411")) }
                    path.startsWith("/v1/settings/shop-identity") -> json(identity)
                    path.startsWith("/v1/me/notification-preferences") && request.method == "PATCH" -> { bodies.add(request.body.readUtf8()); json(prefs.replace("\"email_invoice_paid\":false", "\"email_invoice_paid\":true")) }
                    path.startsWith("/v1/me/notification-preferences") -> json(prefs)
                    path.startsWith("/v1/tenant/integration-health") -> json("""{"twilio_configured":true,"stripe_configured":false,"sendgrid_configured":true,"attachment_backend":"s3"}""")
                    path.startsWith("/v1/reports/category-summary") -> json("""{"watch":{"jobs":2,"billed_cents":10000,"revenue_cents":6000,"cost_cents":0,"outstanding_cents":4000},"shoe":{"jobs":0},"mobile":{"jobs":1,"billed_cents":500,"revenue_cents":500}}""")
                    path.startsWith("/v1/reports/export/sales") -> MockResponse().setHeader("Content-Type", "text/csv").setBody("a,b\n1,2\n")
                    path.startsWith("/v1/reports/activity") -> json("""[{"id":"e1","actor_email":"o@x.co","entity_type":"user","event_type":"x","event_summary":"Did a thing","created_at":"2026-10-01T00:00:00Z"}]""")
                    path.startsWith("/v1/customer-orders/import/sheets") -> json("""["Sheet1","Orders"]""")
                    path.startsWith("/v1/customer-orders/import") -> { bodies.add(request.body.readUtf8()); json("""{"dry_run":${path.contains("dry_run=true")},"total_rows":3,"imported":2,"skipped":1,"skipped_reasons":{"no title":1}}""") }
                    path.startsWith("/v1/users/") && request.method == "DELETE" -> MockResponse().setResponseCode(204)
                    path.startsWith("/v1/users") -> json("""[{"id":"u1","full_name":"Tess","role":"tech","is_active":true,"email":"t@x.co"}]""")
                    path.startsWith("/v1/reports/auto-key/commission") -> json("""{"technicians":[]}""")
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("oa", "owner"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun shopIdentitySavesEditedFieldsAndRejectsBadColour() {
        val model = OwnerSettingsViewModel(); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals("Test Shop", model.state.value.identity!!.name)
        model.saveIdentity("1", "0411", "a@b.co", "", "", "red")
        Assert.assertNotNull(model.state.value.identityError)
        Assert.assertTrue(bodies.none { it.contains("brand_color") })
        model.saveIdentity("1", "0411", "a@b.co", "Pay by card", "", "#aabbcc")
        compose.waitUntil(10_000) { model.state.value.identityInfo != null }
        Assert.assertEquals("0411", model.state.value.identity!!.shopPhone)
        Assert.assertTrue(bodies.any { it.contains("\"shop_phone\":\"0411\"") && it.contains("#aabbcc") })
    }

    @Test fun notificationPrefToggleUsesServerAnswer() {
        val model = OwnerSettingsViewModel(); compose.waitUntil(10_000) { model.state.value.prefs != null }
        Assert.assertTrue(model.state.value.prefs!!.quoteApproved)
        model.setPref("email_invoice_paid", true)
        compose.waitUntil(10_000) { model.state.value.prefs?.invoicePaid == true }
        Assert.assertTrue(bodies.any { it.contains("\"email_invoice_paid\":true") })
        Assert.assertTrue(model.state.value.health!!.twilioConfigured)
    }

    @Test fun categorySummaryAndActivityLoadAndExportDownloads() {
        val model = ReportExtrasViewModel(); compose.waitUntil(10_000) { model.state.value.summary != null && model.state.value.activity.isNotEmpty() }
        Assert.assertEquals(4000L, model.state.value.summary!!.watch!!.outstandingCents)
        model.selectPeriod("quarter"); compose.waitUntil(10_000) { requests.any { it.contains("category-summary") && it.contains("period=quarter") } }
        val csv = kotlinx.coroutines.runBlocking { model.downloadSales("watch") }
        Assert.assertEquals("a,b\n1,2\n", String(csv))
        Assert.assertTrue(requests.any { it.contains("export/sales") && it.contains("category=watch") })
    }

    @Test fun orderImportPicksSheetDryRunsThenImports() {
        val model = OrderImportViewModel()
        model.choose("orders.xlsx", byteArrayOf(1, 2, 3))
        compose.waitUntil(10_000) { model.state.value.sheets.size == 2 }
        model.selectSheet("Orders")
        model.run(true); compose.waitUntil(10_000) { model.state.value.result != null }
        Assert.assertTrue(model.state.value.result!!.dryRun)
        Assert.assertTrue(requests.any { it.contains("dry_run=true") && it.contains("sheet_name=Orders") })
        var imported = false
        model.run(false) { imported = true }; compose.waitUntil(10_000) { imported }
        Assert.assertNull(model.state.value.picked)
        Assert.assertTrue(requests.any { it.contains("dry_run=false") })
    }

    @Test fun csvOrderImportCountsRowsWithoutAskingForSheets() {
        val model = OrderImportViewModel()
        model.choose("orders.csv", "title,supplier\nStrap,A\nPin,B\n".toByteArray())
        Assert.assertEquals(2, model.state.value.picked!!.rowCount)
        Assert.assertTrue(requests.none { it.contains("import/sheets") })
    }

    @Test fun teamDeleteCallsServerAndReloads() {
        val model = TeamViewModel(); compose.waitUntil(10_000) { model.state.value.users.isNotEmpty() && !model.state.value.loading }
        model.delete(TeamUser("u1", "Tess", "tech", true, "t@x.co"))
        compose.waitUntil(10_000) { requests.any { it == "DELETE /v1/users/u1" } && model.state.value.info == "Account deleted." && !model.state.value.busy }
    }
}
