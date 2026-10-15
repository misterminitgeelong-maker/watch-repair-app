package au.mainspring.nativeapp.api

import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Url

/** Generic replay of a queued JSON write. [url] is relative to the API base URL. */
interface OfflineReplayApi {
    @POST suspend fun post(@Url url: String, @Body body: RequestBody): Response<ResponseBody>
    @PUT suspend fun put(@Url url: String, @Body body: RequestBody): Response<ResponseBody>
    @PATCH suspend fun patch(@Url url: String, @Body body: RequestBody): Response<ResponseBody>
}
