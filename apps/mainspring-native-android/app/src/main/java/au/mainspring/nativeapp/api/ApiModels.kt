package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName

data class LoginRequest(
    @SerializedName("tenant_slug") val tenantSlug: String,
    val email: String,
    val password: String,
)

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String?,
    @SerializedName("expires_in_seconds") val expiresInSeconds: Int?,
)

data class SessionUser(
    @SerializedName("full_name") val fullName: String,
    val email: String,
    val role: String,
)

data class SessionResponse(
    val user: SessionUser,
    @SerializedName("tenant_slug") val tenantSlug: String,
    @SerializedName("plan_code") val planCode: String,
)

data class CustomerRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("full_name") val fullName: String,
    val email: String?,
    val phone: String?,
    val address: String?,
    val notes: String?,
    @SerializedName("created_at") val createdAt: String,
)

data class RepairJobRead(
    val id: String,
    @SerializedName("tenant_id") val tenantId: String,
    @SerializedName("watch_id") val watchId: String,
    @SerializedName("job_number") val jobNumber: String,
    val title: String,
    val description: String?,
    val status: String,
    val priority: String,
    @SerializedName("customer_name") val customerName: String?,
    @SerializedName("created_at") val createdAt: String,
)
