package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.NetworkMessagesScreen
import com.google.gson.JsonParser
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Native hub/DM/announcement flows, unread receipts and the notification conversation target. */
class NetworkCommunityParityTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val writes = ConcurrentLinkedQueue<Pair<String, String>>()
    @Volatile private var hubRead = false
    @Volatile private var directRead = false
    @Volatile private var confirmed = false
    @Volatile private var announcementRead = false
    private val network = "11111111-1111-4111-8111-111111111111"
    private val conversation = "22222222-2222-4222-8222-222222222222"
    private fun post(id: String, text: String, mine: Boolean = false, conv: String? = null): String = """{"id":"$id","body":"$text","mine":$mine,"created_at":"2026-11-10T02:00:00Z","sender_name":"Alex","shop_name":"Chadstone","kind":"message","pinned":false,"can_moderate":$mine,"attachments":[],"conversation_id":${conv?.let { "\"$it\"" } ?: "null"}}"""
    private fun announcement() = """{"id":"a1","title":"Training update","body":"Please read the new repair instructions.","state_code":"VIC","category":"training","pinned":true,"requires_confirmation":true,"created_at":"2026-11-10T01:00:00Z","author_name":"Support Office","read":$announcementRead,"confirmed":$confirmed,"can_view_receipts":false}"""
    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear(); NetworkUnreadStore.clear()
        writes.clear(); hubRead = false; directRead = false; confirmed = false; announcementRead = false
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.requestUrl!!.encodedPath
                val json = MockResponse().setHeader("Content-Type", "application/json")
                val body = if(request.method == "POST") request.body.readUtf8().also { writes += path to it } else ""
                return when {
                    path == "/v1/network-community/networks" -> json.setBody("""[{"id":"$network","name":"Minit","own_state":"VIC","can_post":true}]""")
                    path == "/v1/network-community/$network/hubs" -> json.setBody("""[{"code":"VIC","name":"Victoria","mine":true,"accessible":true,"can_post":true,"unread":${if(hubRead) 0 else 2}},{"code":"NSW","name":"New South Wales","mine":false,"accessible":false,"can_post":false,"unread":0},{"code":"QLD","name":"Queensland","mine":false,"accessible":true,"can_post":true,"unread":0}]""")
                    path == "/v1/network-messages/contacts" -> json.setBody("""[{"tenant_id":"other-shop","name":"Chadstone","network_role":"retail","state_code":"VIC","shop_number":"123"}]""")
                    path == "/v1/network-messages/conversations" -> json.setBody("""[{"id":"$conversation","parent_account_id":"$network","other_tenant_id":"other-shop","other_name":"Chadstone","last_body":"Ready for pickup","last_message_at":"2026-11-10T02:00:00Z","unread":${if(directRead) 0 else 3}}]""")
                    path == "/v1/network-community/unread" -> json.setBody("""{"count":${(if(hubRead) 0 else 2) + (if(announcementRead) 0 else 1)}}""")
                    path == "/v1/inbox/count" -> json.setBody("""{"count":0}""")
                    path == "/v1/network-community/$network/hubs/VIC/messages" -> {
                        val earlier = request.requestUrl!!.queryParameter("before") != null
                        json.setBody(if(earlier) """{"messages":[${post("h0", "Earlier stock advice")}],"next_before":null}""" else """{"messages":[${post("h1", "Need soles")}],"next_before":"h1"}""")
                    }
                    path == "/v1/network-community/$network/hubs/VIC/read" -> { hubRead = true; MockResponse().setResponseCode(204) }
                    path == "/v1/network-community/$network/hubs/VIC/posts" -> json.setBody(post("h2", "One pair available", true))
                    path == "/v1/network-messages/conversations/$conversation/messages" -> { directRead = true; json.setBody("[${post("d1", "Ready for pickup", conv = conversation)}]") }
                    path == "/v1/network-community/$network/direct/other-shop/posts" -> json.setBody(post("d2", "Can you help?", true, conversation))
                    path == "/v1/network-community/$network/announcements" -> json.setBody("""{"announcements":[${announcement()}],"has_more":false}""")
                    path == "/v1/network-community/$network/announcements/a1/receipt" -> { announcementRead = true; confirmed = JsonParser.parseString(body).asJsonObject["confirm"].asBoolean; json.setBody(announcement()) }
                    else -> MockResponse().setResponseCode(404)
                }
            }
        }
        server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("network", "tech"); TokenStore.setSessionRole("tech")
    }
    @After fun cleanup() { TokenStore.clear(); NetworkUnreadStore.clear(); server.shutdown() }
    private fun awaitTag(tag: String) = compose.waitUntil(10_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }
    @Test fun chatsPrioritisePrivateConversationsAndKeepTheFullHubListInItsOwnTab() {
        compose.setContent { MainspringTheme { NetworkMessagesScreen({}) } }
        awaitTag("network-conversation-$conversation"); awaitTag("network-hub-VIC")
        val direct = compose.onNodeWithTag("network-conversation-$conversation").fetchSemanticsNode().boundsInRoot
        val ownHub = compose.onNodeWithTag("network-hub-VIC").fetchSemanticsNode().boundsInRoot
        Assert.assertTrue("Private conversations precede state hubs", direct.bottom < ownHub.top)
        compose.onNodeWithTag("network-hub-QLD").assertDoesNotExist()
        compose.onNodeWithTag("network-tab-hubs").performClick()
        awaitTag("network-hub-QLD")
        compose.onNodeWithTag("network-hub-NSW").assertIsNotEnabled()
    }
    @Test fun aHubPinnedFilterDoesNotHidePrivateMessagesAndPhoneComposerStaysBelowTheThread() {
        val vm = NetworkMessagesViewModel()
        compose.setContent { MainspringTheme { NetworkMessagesScreen({}, vm = vm) } }
        awaitTag("network-hub-VIC"); compose.onNodeWithTag("network-hub-VIC").performClick(); awaitTag("network-post-h1")
        compose.onNodeWithText("Pinned messages").performClick()
        compose.onNodeWithTag("network-post-h1").assertDoesNotExist()
        compose.runOnIdle { vm.openDirect("other-shop", "Chadstone", conversation) }
        awaitTag("network-post-d1")
        compose.onNodeWithTag("network-send").assertIsNotEnabled()
        compose.onNodeWithTag("network-draft").performTextInput("Can you help?")
        compose.onNodeWithTag("network-send").assertIsEnabled().performClick()
        awaitTag("network-post-d2")
        val incoming = compose.onNodeWithTag("network-post-d1").fetchSemanticsNode().boundsInRoot
        val outgoing = compose.onNodeWithTag("network-post-d2").fetchSemanticsNode().boundsInRoot
        val composer = compose.onNodeWithTag("network-draft").fetchSemanticsNode().boundsInRoot
        Assert.assertTrue("Outgoing bubbles align to the right", outgoing.center.x > incoming.center.x)
        Assert.assertTrue("Composer is anchored below messages", composer.top > outgoing.bottom)
    }
    @Test fun hubMarksTheVisibleMessageReadAndSendsAPost() {
        compose.setContent { MainspringTheme { NetworkMessagesScreen({}) } }
        awaitTag("network-hub-VIC"); compose.onNodeWithTag("network-hub-VIC").performClick()
        awaitTag("network-post-h1")
        saveNativeQaImage(compose.onRoot(), "parity-20261111-network-hub.png")
        compose.waitUntil(10_000) { writes.any { it.first.endsWith("/read") } }
        Assert.assertEquals("h1", JsonParser.parseString(writes.first { it.first.endsWith("/read") }.second).asJsonObject["message_id"].asString)
        compose.onNodeWithTag("network-draft").performTextInput("One pair available")
        compose.onNodeWithTag("network-send").performClick()
        compose.waitUntil(10_000) { writes.any { it.first.endsWith("/posts") } }
        val sent = writes.first { it.first.endsWith("/posts") }.second
        Assert.assertTrue(sent.contains("One pair available")); Assert.assertTrue(sent.contains("name=\"kind\""))
        awaitTag("network-post-h2")
    }
    @Test fun conversationNotificationOpensTheActualDirectThreadAndClearsItsUnreadCount() {
        Assert.assertEquals("networkMessages?conversation=$conversation", PushRoutes.toRoute("/messages?c=$conversation"))
        compose.setContent { MainspringTheme { NetworkMessagesScreen({}, conversation = conversation) } }
        awaitTag("network-post-d1")
        compose.onNodeWithText("Private to the two participating sites.").assertExists()
        compose.onNodeWithTag("network-draft").performTextInput("Can you help?"); compose.onNodeWithTag("network-send").performClick()
        compose.waitUntil(10_000) { writes.any { it.first.endsWith("/direct/other-shop/posts") } }
        runBlocking { NetworkUnreadStore.refresh() }
        Assert.assertEquals(3, NetworkUnreadStore.count.value) // two hub posts plus one announcement remain.
    }
    @Test fun announcementConfirmationRecordsTheShopReceiptAndUpdatesUnread() {
        compose.setContent { MainspringTheme { NetworkMessagesScreen({}, initialTab = "announcements") } }
        awaitTag("network-confirm-a1")
        compose.onNodeWithTag("network-confirm-a1").performScrollTo().performClick()
        compose.waitUntil(10_000) { confirmed }
        compose.waitUntil(10_000) { compose.onAllNodesWithText("Confirmed ✓").fetchSemanticsNodes().isNotEmpty() }
        val body = JsonParser.parseString(writes.first { it.first.endsWith("/receipt") }.second).asJsonObject
        Assert.assertTrue(body["confirm"].asBoolean)
        runBlocking { NetworkUnreadStore.refresh() }
        Assert.assertEquals(5, NetworkUnreadStore.count.value) // two hub posts and three direct messages remain.
    }
    @Test fun aLatestPageRefreshKeepsTheEarlierHubHistoryAlreadyLoaded() {
        val vm = NetworkMessagesViewModel()
        compose.setContent { MainspringTheme { NetworkMessagesScreen({}, vm = vm) } }
        awaitTag("network-hub-VIC"); compose.onNodeWithTag("network-hub-VIC").performClick(); awaitTag("network-post-h1")
        compose.onNodeWithText("Load earlier messages").performScrollTo().performClick(); awaitTag("network-post-h0")
        compose.runOnIdle { vm.refresh() }
        compose.waitUntil(10_000) { !vm.state.value.loading }
        compose.onNodeWithTag("network-post-h0").assertExists(); compose.onNodeWithTag("network-post-h1").assertExists()
    }
}
