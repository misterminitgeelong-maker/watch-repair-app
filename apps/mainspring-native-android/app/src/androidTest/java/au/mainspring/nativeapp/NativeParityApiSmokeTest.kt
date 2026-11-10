package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.*
import org.junit.Assume
import org.junit.Test

/** Typed native clients against the actual disposable backend, never a production API or delivery provider. */
class NativeParityApiSmokeTest {
    @Test fun nativeParityModulesRoundTripThroughRealApi() = runBlocking {
        val args = InstrumentationRegistry.getArguments()
        val base = args.getString("localApiBaseUrl")
        Assume.assumeTrue("Requires qa/local_backend.py and qa/seed_parity.py", base != null)
        require(base == "http://127.0.0.1:8716/")
        val slug = requireNotNull(args.getString("localTenantSlug"))
        val email = requireNotNull(args.getString("localOwnerEmail"))
        require(slug.startsWith("native-qa-") && email.endsWith("@native.example.test"))
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        try {
            TokenStore.saveApiBaseUrl(base)
            val login = ApiClient.api.login(LoginRequest(slug, email, "Native-local-test-only!"))
            TokenStore.saveTokens(login.accessToken, login.refreshToken)
            val session = ApiClient.api.session()
            assertEquals(slug, session.tenantSlug)
            TokenStore.setDraftScope(session.tenantId, session.user.id); TokenStore.setSessionRole(session.user.role)
            val network = ApiClient.service(NetworkApi::class.java)
            val n = network.networks().first()
            val hub = network.hubs(n.id).first { it.accessible && it.canPost }
            val body = "Native integration check".toRequestBody("text/plain".toMediaType())
            val post = network.sendHub(n.id, hub.code, body, "message".toRequestBody("text/plain".toMediaType()), null, emptyList())
            assertTrue(network.hubMessages(n.id, hub.code).messages.any { it.id == post.id && it.body == "Native integration check" })
            assertTrue(network.readHub(n.id, hub.code, JsonObject().apply { addProperty("message_id", post.id) }).isSuccessful)
            val recipient = network.contacts(n.id).first()
            val direct = network.sendDirect(n.id, recipient.tenantId, body, emptyList())
            assertTrue(network.directMessages(requireNotNull(direct.conversationId)).any { it.id == direct.id })
            val notice = network.announcements(n.id).announcements.first()
            val receipt = network.receipt(n.id, notice.id, JsonObject().apply { addProperty("confirm", true) })
            assertTrue(receipt.read); assertTrue(receipt.confirmed)

            val parent = ApiClient.service(MyShopsApi::class.java)
            assertEquals(n.id, parent.summary().id)
            assertTrue(parent.shops().sites.any { it.id == session.tenantId })
            parent.activity(); parent.invitations()

            val parts = ApiClient.service(PartsApi::class.java)
            val location = parts.locations().first { it.mine && it.active }
            assertTrue(parts.models().isNotEmpty())
            val level = parts.levels().first { it.locationId == location.id }
            parts.adjust(PartAdjustment(location.id, level.sku, level.quantity + 2, "set_count", "Native QA count"))
            assertEquals(level.quantity + 2, parts.levels().first { it.partId == level.partId && it.locationId == location.id }.quantity)
            parts.adjust(PartAdjustment(location.id, level.sku, level.quantity, "set_count", "Restore QA count"))
            assertTrue(parts.purchases("DEMO").isNotEmpty())
            val shoe = ApiClient.api.listShoeRepairJobs().first { it.shoe?.brand == "Birkenstock" }
            assertFalse(shoe.shoe?.modelName.isNullOrBlank())
            assertFalse(shoe.shoe?.warrantyStatus.isNullOrBlank())
            val suggestion = parts.suggested(shoe.id).first()
            val used = parts.use(shoe.id, ShoePartUse(suggestion.id, 1, location.id))
            assertTrue(parts.used(shoe.id).any { it.id == used.id })

            val engraving = ApiClient.service(EngravingApi::class.java)
            val event = engraving.createEvent(JsonObject().apply { addProperty("name", "Native QA engraving"); addProperty("price_cents", 1500); addProperty("minutes_per_medal", 3); addProperty("sms_enabled", false); addProperty("online_payments", false) })
            val order = engraving.walkUp(event.id, JsonObject().apply { addProperty("athlete_name", "Native QA athlete"); addProperty("place", "1st"); addProperty("qty", 1); addProperty("paid", true) })
            assertTrue(engraving.queue(event.id).orders.any { it.id == order.id })
            assertTrue(engraving.export(event.id, "csv").use { it.string() }.contains("Native QA athlete"))
            assertEquals("engraving", engraving.action(order.id, "start").status)
            assertEquals("ready", engraving.action(order.id, "medal-done").status)
            assertEquals("collected", engraving.updateOrder(order.id, JsonObject().apply { addProperty("status", "collected"); addProperty("paid", true) }).status)

            val integrations = ApiClient.service(IntegrationsApi::class.java)
            val key = integrations.createApiKey(ApiKeyCreateBody("Native QA key"))
            assertFalse(key.apiKey.isNullOrBlank())
            assertTrue(integrations.apiKeys().any { it.id == key.id })
            assertTrue(integrations.revokeApiKey(key.id).isSuccessful)
            assertTrue(integrations.apiKeys().none { it.id == key.id && it.isActive })
            val config = ApiClient.service(ClientConfigApi::class.java).config()
            assertEquals(0, config.minimum); assertNull(config.sentryDsn)
        } finally { TokenStore.clear() }
    }
}
