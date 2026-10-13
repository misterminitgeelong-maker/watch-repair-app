package au.mainspring.nativeapp.api

import au.mainspring.nativeapp.TokenStore
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import okhttp3.HttpUrl.Companion.toHttpUrl

/**
 * On 401, exchanges the refresh token once and retries the request.
 * Skips login/refresh endpoints to avoid loops.
 */
class TokenAuthenticator(
    private val refreshApi: RefreshApi,
    expectedBaseUrl: String = ApiClient.getEffectiveBaseUrl(),
) : Authenticator {
    private val origin = expectedBaseUrl.toHttpUrl()

    override fun authenticate(route: Route?, response: Response): Request? {
        val destination = response.request.url
        // Authenticated file endpoints may redirect to signed storage. Never retry those hosts with shop tokens.
        if(destination.scheme != origin.scheme || destination.host != origin.host || destination.port != origin.port) return null
        val path = response.request.url.encodedPath
        if (path.endsWith("/v1/auth/login") ||
            path.endsWith("/v1/auth/multi-site-login") ||
            path.endsWith("/v1/auth/refresh")
        ) {
            return null
        }
        if (response.request.header("X-Auth-Retry") != null) {
            return null
        }
        synchronized(this) {
            val snapshot = TokenStore.sessionSnapshot()
            val requestGeneration = response.request.tag(SessionGenerationTag::class.java)?.generation ?: return null
            if(requestGeneration != snapshot.generation) return null
            val latest = snapshot.access
            if (latest != null && response.request.header("Authorization") != "Bearer $latest") {
                return response.request.newBuilder().header("Authorization", "Bearer $latest").header("X-Auth-Retry", "1").build()
            }
            val refresh = snapshot.refresh ?: run {
                TokenStore.expireSession(requestGeneration)
                return null
            }
            val call = refreshApi.refresh(RefreshRequest(refresh))
            val tokenResp = try {
                call.execute()
            } catch (e: java.io.IOException) {
                throw e
            }
            if(TokenStore.sessionGeneration() != requestGeneration) { tokenResp.errorBody()?.close(); return null }
            if (!tokenResp.isSuccessful || tokenResp.body() == null) {
                val code = tokenResp.code()
                tokenResp.errorBody()?.close()
                if (code == 401 || code == 403) { TokenStore.expireSession(requestGeneration); return null }
                throw java.io.IOException("Your shop's session service is temporarily unavailable.")
            }
            val body = tokenResp.body()!!
            if(!TokenStore.saveRefreshedTokens(body.accessToken, body.refreshToken, requestGeneration)) return null
            return response.request.newBuilder()
                .removeHeader("Authorization")
                .header("Authorization", "Bearer ${body.accessToken}")
                .header("X-Auth-Retry", "1")
                .build()
        }
    }
}
