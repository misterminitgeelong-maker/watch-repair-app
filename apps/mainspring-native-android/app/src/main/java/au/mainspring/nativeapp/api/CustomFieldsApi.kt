package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.Path

/** Body of the web's `patchJobCustomFields`: free-form string key/value pairs replacing the job's whole set. */
data class CustomFieldsBody(val fields: Map<String, String>)
data class CustomFieldsResult(val ok: Boolean = true, val fields: Map<String, String> = emptyMap())

/**
 * Per-job custom fields (web: JobCustomFields). The backend stores them as `custom_fields_json` on the job and has no
 * field-definition or settings endpoint, so there is nothing to configure: techs and owners add arbitrary names per job.
 * Jobs are read as raw JSON because the shared job models do not carry `custom_fields_json`.
 */
interface CustomFieldsApi {
    @GET("v1/repair-jobs/{id}") suspend fun repairJob(@Path("id") id: String): JsonObject
    @GET("v1/shoe-repair-jobs/{id}") suspend fun shoeJob(@Path("id") id: String): JsonObject
    @GET("v1/auto-key-jobs/{id}") suspend fun autoKeyJob(@Path("id") id: String): JsonObject
    @PATCH("v1/repair-jobs/{id}/custom-fields") suspend fun saveRepairJob(@Path("id") id: String, @Body body: CustomFieldsBody): CustomFieldsResult
    @PATCH("v1/shoe-repair-jobs/{id}/custom-fields") suspend fun saveShoeJob(@Path("id") id: String, @Body body: CustomFieldsBody): CustomFieldsResult
    @PATCH("v1/auto-key-jobs/{id}/custom-fields") suspend fun saveAutoKeyJob(@Path("id") id: String, @Body body: CustomFieldsBody): CustomFieldsResult
}
