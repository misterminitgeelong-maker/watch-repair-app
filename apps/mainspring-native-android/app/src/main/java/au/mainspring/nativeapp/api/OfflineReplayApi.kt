package au.mainspring.nativeapp.api

import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.HeaderMap
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Url

/**
 * Generic replay of a queued JSON write. [url] is relative to the API base URL.
 * [headers] carries `Idempotency-Key` and, for stale-write protection, `X-Expected-Updated-At`.
 */
interface OfflineReplayApi {
    @POST suspend fun post(@Url url: String, @Body body: RequestBody, @HeaderMap headers: Map<String, String>): Response<ResponseBody>
    @PUT suspend fun put(@Url url: String, @Body body: RequestBody, @HeaderMap headers: Map<String, String>): Response<ResponseBody>
    @PATCH suspend fun patch(@Url url: String, @Body body: RequestBody, @HeaderMap headers: Map<String, String>): Response<ResponseBody>
    /** Pre-replay read of a job, to compare its live status before a queued status change is sent. */
    @GET suspend fun get(@Url url: String): Response<ResponseBody>
}
