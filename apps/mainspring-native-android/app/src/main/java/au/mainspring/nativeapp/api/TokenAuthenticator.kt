package au.mainspring.nativeapp.api

import au.mainspring.nativeapp.TokenStore
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route

/**
 * On 401, exchanges the refresh token once and retries the request.
 * Skips login/refresh endpoints to avoid loops.
 */
class TokenAuthenticator(
    private val refreshApi: RefreshApi,
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
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
            val refresh = TokenStore.getRefreshToken() ?: run {
                TokenStore.clear()
                return null
            }
            val call = refreshApi.refresh(RefreshRequest(refresh))
            val tokenResp = try {
                call.execute()
            } catch (_: Exception) {
                TokenStore.clear()
                return null
            }
            if (!tokenResp.isSuccessful || tokenResp.body() == null) {
                TokenStore.clear()
                return null
            }
            val body = tokenResp.body()!!
            TokenStore.saveTokens(body.accessToken, body.refreshToken)
            return response.request.newBuilder()
                .removeHeader("Authorization")
                .header("Authorization", "Bearer ${body.accessToken}")
                .header("X-Auth-Retry", "1")
                .build()
        }
    }
}
