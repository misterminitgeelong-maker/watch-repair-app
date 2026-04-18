package au.mainspring.nativeapp.api

import au.mainspring.nativeapp.TokenStore
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Attaches Bearer token for authenticated routes. Login and other public POSTs
 * run without a stored token, so no header is added until after sign-in.
 */
class AuthInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val path = chain.request().url.encodedPath
        if (path.endsWith("/v1/auth/login") || path.endsWith("/v1/auth/multi-site-login")) {
            return chain.proceed(chain.request())
        }
        val token = TokenStore.getAccessToken()
        val request = if (token.isNullOrBlank()) {
            chain.request()
        } else {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        }
        return chain.proceed(request)
    }
}
