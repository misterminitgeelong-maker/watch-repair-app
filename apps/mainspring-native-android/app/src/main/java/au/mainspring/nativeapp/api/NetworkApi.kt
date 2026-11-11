package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

data class MessagingNetwork(val id: String, val name: String,
    @SerializedName("own_state") val ownState: String? = null,
    @SerializedName("can_post") val canPost: Boolean = false)
data class StateHub(val code: String, val name: String, val mine: Boolean = false,
    val accessible: Boolean = false, @SerializedName("can_post") val canPost: Boolean = false, val unread: Int = 0)
data class NetworkContact(@SerializedName("tenant_id") val tenantId: String, val name: String,
    @SerializedName("network_role") val role: String, @SerializedName("state_code") val state: String? = null,
    @SerializedName("shop_number") val shopNumber: String? = null)
data class NetworkConversation(val id: String, @SerializedName("parent_account_id") val networkId: String,
    @SerializedName("other_tenant_id") val otherTenantId: String, @SerializedName("other_name") val otherName: String,
    @SerializedName("last_body") val lastBody: String? = null, @SerializedName("last_message_at") val lastAt: String,
    val unread: Int = 0)
data class ChatAttachment(val id: String, val filename: String,
    @SerializedName("content_type") val contentType: String, @SerializedName("size_bytes") val size: Long)
data class NetworkPost(val id: String, val body: String, val mine: Boolean = false,
    @SerializedName("conversation_id") val conversationId: String? = null,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("sender_name") val senderName: String? = null,
    @SerializedName("shop_name") val shopName: String? = null,
    val kind: String? = null, val pinned: Boolean = false,
    @SerializedName("resolved_at") val resolvedAt: String? = null,
    @SerializedName("reply_preview") val replyPreview: String? = null,
    @SerializedName("can_moderate") val canModerate: Boolean = false,
    val attachments: List<ChatAttachment> = emptyList())
data class HubPage(val messages: List<NetworkPost>, @SerializedName("next_before") val nextBefore: String? = null)
data class NetworkAnnouncement(val id: String, val title: String, val body: String,
    @SerializedName("state_code") val state: String? = null, val category: String, val pinned: Boolean = false,
    @SerializedName("requires_confirmation") val requiresConfirmation: Boolean = false,
    @SerializedName("created_at") val createdAt: String, @SerializedName("author_name") val author: String,
    val read: Boolean = false, val confirmed: Boolean = false,
    @SerializedName("can_view_receipts") val canViewReceipts: Boolean = false)
data class AnnouncementPage(val announcements: List<NetworkAnnouncement>, @SerializedName("has_more") val hasMore: Boolean = false)
data class NetworkUnread(val count: Int = 0)

interface NetworkApi {
    @GET("v1/network-community/networks") suspend fun networks(): List<MessagingNetwork>
    @GET("v1/network-community/unread") suspend fun unread(): NetworkUnread
    @GET("v1/network-community/{network}/hubs") suspend fun hubs(@Path("network") network: String): List<StateHub>
    @GET("v1/network-messages/contacts") suspend fun contacts(@Query("parent_account_id") network: String): List<NetworkContact>
    @GET("v1/network-messages/conversations") suspend fun conversations(@Query("parent_account_id") network: String? = null): List<NetworkConversation>
    @GET("v1/network-messages/conversations/{id}/messages") suspend fun directMessages(@Path("id") id: String): List<NetworkPost>
    @GET("v1/network-community/{network}/hubs/{code}/messages") suspend fun hubMessages(@Path("network") network: String, @Path("code") code: String, @Query("before") before: String? = null): HubPage
    @POST("v1/network-community/{network}/hubs/{code}/read") suspend fun readHub(@Path("network") network: String, @Path("code") code: String, @Body body: JsonObject): Response<Unit>
    @PATCH("v1/network-community/{network}/hubs/{code}/messages/{id}") suspend fun updateHub(@Path("network") network: String, @Path("code") code: String, @Path("id") id: String, @Body body: JsonObject): NetworkPost
    @DELETE("v1/network-community/{network}/hubs/{code}/messages/{id}") suspend fun deleteHub(@Path("network") network: String, @Path("code") code: String, @Path("id") id: String): Response<Unit>
    @Multipart @POST("v1/network-community/{network}/hubs/{code}/posts") suspend fun sendHub(@Path("network") network: String, @Path("code") code: String, @Part("body") body: RequestBody, @Part("kind") kind: RequestBody, @Part("reply_to_id") reply: RequestBody?, @Part files: List<MultipartBody.Part>): NetworkPost
    @Multipart @POST("v1/network-community/{network}/direct/{tenant}/posts") suspend fun sendDirect(@Path("network") network: String, @Path("tenant") tenant: String, @Part("body") body: RequestBody, @Part files: List<MultipartBody.Part>): NetworkPost
    @GET("v1/network-community/{network}/announcements") suspend fun announcements(@Path("network") network: String, @Query("offset") offset: Int = 0): AnnouncementPage
    @POST("v1/network-community/{network}/announcements/{id}/receipt") suspend fun receipt(@Path("network") network: String, @Path("id") id: String, @Body body: JsonObject): NetworkAnnouncement
    @GET("v1/network-community/{network}/announcements/{id}/receipts") suspend fun receipts(@Path("network") network: String, @Path("id") id: String): JsonObject
    @GET("v1/network-community/{network}/announcements/{id}/receipts") suspend fun receiptCsv(@Path("network") network: String, @Path("id") id: String, @Query("export") format: String = "csv"): ResponseBody
    @GET("v1/network-community/attachments/{id}") suspend fun attachment(@Path("id") id: String): ResponseBody
}
