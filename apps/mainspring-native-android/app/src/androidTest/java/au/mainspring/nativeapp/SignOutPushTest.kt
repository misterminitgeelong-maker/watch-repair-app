package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.SignOutClient
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert
import org.junit.Before
import org.junit.Test

/** Signing out removes this phone's push token from the server before the session is revoked. */
class SignOutPushTest {
    private lateinit var server: MockWebServer
    @Before fun setup() { server = MockWebServer(); server.enqueue(MockResponse().setResponseCode(204)); server.enqueue(MockResponse().setResponseCode(204)); server.start() }
    @After fun cleanup() { server.shutdown() }

    @Test fun signOutDeletesTheDeviceTokenThenRevokesTheSession() = runBlocking {
        SignOutClient.revoke(server.url("/").toString(), "access-token-1", "push-token-abcdefghijklmnop")
        val first = server.takeRequest(); val second = server.takeRequest()
        Assert.assertEquals("DELETE", first.method); Assert.assertEquals("/v1/me/devices?token=push-token-abcdefghijklmnop", first.path)
        Assert.assertEquals("Bearer access-token-1", first.getHeader("Authorization"))
        Assert.assertEquals("POST", second.method); Assert.assertEquals("/v1/auth/logout", second.path)
    }

    @Test fun signOutWithoutAPushTokenOnlyRevokesTheSession() = runBlocking {
        SignOutClient.revoke(server.url("/").toString(), "access-token-1", null)
        val only = server.takeRequest()
        Assert.assertEquals("/v1/auth/logout", only.path)
        Assert.assertEquals(1, server.requestCount)
    }
}
