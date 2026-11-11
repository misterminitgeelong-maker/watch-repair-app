package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

/** One shop API key as listed by `GET tenant/api-keys`; the secret itself is never returned after creation. */
data class TenantApiKey(
    val id: String, val name: String,
    @SerializedName("key_prefix") val keyPrefix: String,
    @SerializedName("is_active") val isActive: Boolean = true,
    @SerializedName("created_at") val createdAt: String? = null,
)
data class ApiKeyCreateBody(val name: String)
/** `POST tenant/api-keys`: [apiKey] is the full secret and is only ever shown here, once. */
data class ApiKeyCreated(val id: String, val name: String, @SerializedName("key_prefix") val keyPrefix: String, @SerializedName("api_key") val apiKey: String)

/** One outbound webhook subscription; [eventTypes] is a comma-separated list (`*` means every event). */
data class TenantWebhook(
    val id: String, val url: String,
    @SerializedName("event_types") val eventTypes: String = "",
    @SerializedName("is_active") val isActive: Boolean = true,
    @SerializedName("created_at") val createdAt: String? = null,
)
data class WebhookCreateBody(val url: String, @SerializedName("event_types") val eventTypes: List<String>)

/** Web `TenantQolSettings` API keys and outbound webhooks. Listing is open to technicians; create and delete are manager and above. */
interface IntegrationsApi {
    @GET("v1/tenant/api-keys") suspend fun apiKeys(): List<TenantApiKey>
    @POST("v1/tenant/api-keys") suspend fun createApiKey(@Body body: ApiKeyCreateBody): ApiKeyCreated
    @DELETE("v1/tenant/api-keys/{id}") suspend fun revokeApiKey(@Path("id") id: String): Response<Unit>
    @GET("v1/tenant/webhooks") suspend fun webhooks(): List<TenantWebhook>
    @POST("v1/tenant/webhooks") suspend fun createWebhook(@Body body: WebhookCreateBody): TenantWebhook
    @DELETE("v1/tenant/webhooks/{id}") suspend fun deleteWebhook(@Path("id") id: String): Response<Unit>
}
