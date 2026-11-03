package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.IntegrationsScreen
import com.google.gson.JsonParser
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** API keys and outbound webhooks on the native screen, against a mock server. */
class IntegrationsScreenTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val calls = ConcurrentLinkedQueue<String>()
    private val bodies = ConcurrentLinkedQueue<String>()
    private val keys = java.util.concurrent.CopyOnWriteArrayList<String>()
    private val hooks = java.util.concurrent.CopyOnWriteArrayList<String>()
    @Volatile private var createStatus = 201

    private fun keyJson(id: String, name: String) = """{"id":"$id","name":"$name","key_prefix":"msk_abcd1234","is_active":true,"created_at":"2026-11-01T00:00:00Z"}"""
    private fun hookJson(id: String, url: String, events: String) = """{"id":"$id","url":"$url","event_types":"$events","is_active":true,"created_at":"2026-11-01T00:00:00Z"}"""

    @Before fun setup() {
        keys.add(keyJson("k1", "Zapier")); hooks.add(hookJson("h1", "https://hooks.example.test/a", "quote_approved"))
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath; val key = "${request.method} $path"
                val json = MockResponse().setHeader("Content-Type", "application/json")
                return when {
                    key == "GET /v1/tenant/api-keys" -> json.setBody("[${keys.joinToString(",")}]")
                    key == "GET /v1/tenant/webhooks" -> json.setBody("[${hooks.joinToString(",")}]")
                    key == "POST /v1/tenant/api-keys" -> { calls.add(key); bodies.add(request.body.readUtf8()); keys.add(0, keyJson("k2", "Reports")); json.setResponseCode(201).setBody("""{"id":"k2","name":"Reports","key_prefix":"msk_zzzz9999","api_key":"msk_zzzz9999_FULL_SECRET_VALUE"}""") }
                    key == "DELETE /v1/tenant/api-keys/k1" -> { calls.add(key); keys.removeAll { it.contains("\"k1\"") }; MockResponse().setResponseCode(204) }
                    key == "POST /v1/tenant/webhooks" -> { calls.add(key); bodies.add(request.body.readUtf8())
                        if(createStatus == 422) json.setResponseCode(422).setBody("""{"detail":"Webhook URL must use https"}""")
                        else { hooks.add(0, hookJson("h2", "https://hooks.example.test/b", "quote_approved,job_created")); json.setResponseCode(201).setBody(hookJson("h2", "https://hooks.example.test/b", "quote_approved,job_created")) } }
                    key == "DELETE /v1/tenant/webhooks/h1" -> { calls.add(key); hooks.removeAll { it.contains("\"h1\"") }; MockResponse().setResponseCode(204) }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("integrations", "owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    private fun open(role: String) {
        TokenStore.setSessionRole(role)
        compose.setContent { MainspringTheme { IntegrationsScreen(onBack = {}) } }
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("api-key-k1").fetchSemanticsNodes().isNotEmpty() }
    }

    @Test fun listsExistingKeysAndWebhooks() {
        open("owner")
        compose.onNodeWithText("Zapier").assertExists(); compose.onNodeWithText("https://hooks.example.test/a").assertExists()
        compose.onNodeWithText("Events: quote_approved").assertExists()
    }

    @Test fun creatingAKeyShowsTheSecretOnceWithACopyButton() {
        open("manager")
        compose.onNodeWithTag("api-key-name").performTextInput("Reports")
        compose.onNodeWithTag("api-key-create").performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("api-key-created").fetchSemanticsNodes().isNotEmpty() }
        Assert.assertEquals("Reports", JsonParser.parseString(bodies.peek()).asJsonObject["name"].asString)
        compose.onNodeWithTag("api-key-secret").assertTextContains("msk_zzzz9999_FULL_SECRET_VALUE")
        compose.onNodeWithTag("api-key-copy").assertExists()
        compose.onNodeWithTag("api-key-dismiss").performClick()
        compose.onAllNodesWithTag("api-key-created").assertCountEquals(0)
        compose.onAllNodesWithText("msk_zzzz9999_FULL_SECRET_VALUE").assertCountEquals(0)
        compose.onNodeWithTag("api-key-k2").assertExists()
    }

    @Test fun revokingAKeyNeedsConfirmationAndRemovesIt() {
        open("owner")
        compose.onNodeWithTag("api-key-revoke-k1").performScrollTo().performClick()
        compose.onNodeWithText("Revoke this key?").assertExists()
        Assert.assertTrue(calls.isEmpty())
        compose.onNodeWithTag("api-key-revoke-confirm").performClick()
        compose.waitUntil(10_000) { calls.isNotEmpty() }
        Assert.assertEquals("DELETE /v1/tenant/api-keys/k1", calls.peek())
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("api-key-k1").fetchSemanticsNodes().isEmpty() }
    }

    @Test fun addingAWebhookSendsTheEventListAndShowsIt() {
        open("owner")
        compose.onNodeWithTag("webhook-url").performScrollTo().performTextInput("https://hooks.example.test/b")
        compose.onNodeWithTag("webhook-add").performScrollTo().performClick()
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("webhook-h2").fetchSemanticsNodes().isNotEmpty() }
        val body = JsonParser.parseString(bodies.peek()).asJsonObject
        Assert.assertEquals("https://hooks.example.test/b", body["url"].asString)
        Assert.assertEquals(listOf("quote_approved", "job_created"), body.getAsJsonArray("event_types").map { it.asString })
    }

    @Test fun aNonHttpsWebhookIsRefusedBeforeAnythingIsSent() {
        open("owner")
        compose.onNodeWithTag("webhook-url").performScrollTo().performTextInput("http://insecure.example.test")
        compose.onNodeWithTag("webhook-add").performScrollTo().performClick()
        compose.onNodeWithTag("integrations-error").assertExists()
        Assert.assertTrue(calls.isEmpty())
    }

    @Test fun removingAWebhookNeedsConfirmation() {
        open("owner")
        compose.onNodeWithTag("webhook-remove-h1").performScrollTo().performClick()
        compose.onNodeWithText("Remove this webhook?").assertExists()
        compose.onNodeWithTag("webhook-remove-confirm").performClick()
        compose.waitUntil(10_000) { calls.isNotEmpty() }
        Assert.assertEquals("DELETE /v1/tenant/webhooks/h1", calls.peek())
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("webhook-h1").fetchSemanticsNodes().isEmpty() }
    }

    @Test fun techniciansCanSeeButNotChangeAnything() {
        open("tech")
        compose.onNodeWithText("Zapier").assertExists()
        compose.onAllNodesWithTag("api-key-create").assertCountEquals(0)
        compose.onAllNodesWithTag("api-key-revoke-k1").assertCountEquals(0)
        compose.onAllNodesWithTag("webhook-add").assertCountEquals(0)
        compose.onAllNodesWithTag("webhook-remove-h1").assertCountEquals(0)
    }
}
