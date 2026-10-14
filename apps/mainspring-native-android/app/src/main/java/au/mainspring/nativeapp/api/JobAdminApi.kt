package au.mainspring.nativeapp.api

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.DELETE
import retrofit2.http.POST
import retrofit2.http.Path

/** Only the id of a cloned job matters to the app; the create responses carry more fields that are ignored. */
data class ClonedJob(val id: String)

/** Delete and duplicate for watch and shoe repair jobs (mirrors web `deleteJob` / `cloneRepairJob`). */
interface JobAdminApi {
    @DELETE("v1/repair-jobs/{id}") suspend fun deleteRepairJob(@Path("id") id: String): Response<ResponseBody>
    @DELETE("v1/shoe-repair-jobs/{id}") suspend fun deleteShoeJob(@Path("id") id: String): Response<ResponseBody>
    @POST("v1/repair-jobs/{id}/clone") suspend fun cloneRepairJob(@Path("id") id: String): ClonedJob
    @POST("v1/shoe-repair-jobs/{id}/clone") suspend fun cloneShoeJob(@Path("id") id: String): ClonedJob
}
