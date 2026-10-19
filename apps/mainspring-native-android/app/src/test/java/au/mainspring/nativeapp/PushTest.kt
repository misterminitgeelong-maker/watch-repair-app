package au.mainspring.nativeapp

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PushTest {
    private class FakeApi(var fail: Boolean = false) : DeviceRegistryApi {
        val sent = mutableListOf<String>()
        override suspend fun register(token: String) { if(fail) throw java.io.IOException("offline"); sent.add(token) }
    }
    private class FakeStore(var token: String? = null) : DeviceTokenStore {
        override fun get() = token
        override fun save(token: String?) { this.token = token }
    }

    @Test fun registersAndRemembersTheTokenWhenSignedInAndAllowed() = runBlocking {
        val api = FakeApi(); val store = FakeStore()
        assertTrue(DeviceRegistrar(api, store).sync("token-abc-123456789012345", signedIn = true, permitted = true))
        assertEquals(listOf("token-abc-123456789012345"), api.sent)
        assertEquals("token-abc-123456789012345", store.get())
    }

    @Test fun doesNothingWhenSignedOutOrNotAllowedOrNoToken() = runBlocking {
        val api = FakeApi(); val store = FakeStore(); val registrar = DeviceRegistrar(api, store)
        assertFalse(registrar.sync("token-abc-123456789012345", signedIn = false, permitted = true))
        assertFalse(registrar.sync("token-abc-123456789012345", signedIn = true, permitted = false))
        assertFalse(registrar.sync(null, signedIn = true, permitted = true))
        assertFalse(registrar.sync("  ", signedIn = true, permitted = true))
        assertTrue(api.sent.isEmpty()); assertNull(store.get())
    }

    @Test fun refreshedTokenIsRegisteredAndReplacesTheStoredOne() = runBlocking {
        val api = FakeApi(); val store = FakeStore("old-token-12345678901234")
        assertTrue(DeviceRegistrar(api, store).sync("new-token-12345678901234", signedIn = true, permitted = true))
        assertEquals("new-token-12345678901234", store.get())
    }

    @Test fun failedSendKeepsTheOldStoredTokenSoItCanBeRemovedAtSignOut() = runBlocking {
        val api = FakeApi(fail = true); val store = FakeStore("old-token-12345678901234")
        assertFalse(DeviceRegistrar(api, store).sync("new-token-12345678901234", signedIn = true, permitted = true))
        assertEquals("old-token-12345678901234", store.get())
    }

    @Test fun tappedNotificationPathsOpenTheRightScreen() {
        assertEquals("watchJob/abc-123", PushRoutes.toRoute("/jobs/abc-123"))
        assertEquals("watchJob/abc-123", PushRoutes.toRoute("/jobs/abc-123?tab=messages"))
        assertEquals("shoeJob/9f2", PushRoutes.toRoute("/shoe-repairs/9f2"))
        assertEquals("autoKeyJob/77a", PushRoutes.toRoute("/auto-key/77a"))
        assertEquals("invoices", PushRoutes.toRoute("/invoices"))
        assertEquals("inbox", PushRoutes.toRoute("/inbox"))
    }

    @Test fun unknownOrUnsafePathsAreIgnored() {
        assertNull(PushRoutes.toRoute(null))
        assertNull(PushRoutes.toRoute(""))
        assertNull(PushRoutes.toRoute("/customers/abc"))
        assertNull(PushRoutes.toRoute("/jobs/../../etc"))
        assertNull(PushRoutes.toRoute("/jobs/a b"))
        assertNull(PushRoutes.toRoute("https://evil.example/jobs/abc"))
    }

    @Test fun inboxHoldsOneRouteUntilItIsConsumed() {
        PushRouteInbox.clear()
        assertTrue(PushRouteInbox.offer("/jobs/abc"))
        assertEquals("watchJob/abc", PushRouteInbox.pending.value)
        PushRouteInbox.consume("watchJob/other"); assertEquals("watchJob/abc", PushRouteInbox.pending.value)
        PushRouteInbox.consume("watchJob/abc"); assertNull(PushRouteInbox.pending.value)
        assertFalse(PushRouteInbox.offer("/nope"))
    }
}
