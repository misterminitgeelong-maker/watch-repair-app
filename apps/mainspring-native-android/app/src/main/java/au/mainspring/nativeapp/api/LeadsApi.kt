package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/** Mobile services inbound lead inbox (`/v1/prospects/leads`). Obtain via ApiClient.service(LeadsApi::class.java). */
interface LeadsApi {
    @GET("v1/prospects/leads") suspend fun leads(@Query("status") status: String? = null): List<InboundLead>
    @POST("v1/prospects/leads") suspend fun createLead(@Body body: JsonObject): InboundLead
    @PATCH("v1/prospects/leads/{id}") suspend fun updateLead(@Path("id") id: String, @Body body: JsonObject): InboundLead
    @POST("v1/prospects/leads/{id}/convert-to-account") suspend fun convertLead(@Path("id") id: String, @Body body: JsonObject): InboundLead
}

data class InboundLead(
    val id: String,
    val name: String = "",
    val address: String? = null,
    val phone: String? = null,
    val category: String? = null,
    @SerializedName("suburb_name") val suburbName: String? = null,
    @SerializedName("contact_name") val contactName: String? = null,
    @SerializedName("contact_email") val contactEmail: String? = null,
    val notes: String? = null,
    val status: String = "new",
    /** "prospected" or "website_lead" */
    val source: String? = null,
    @SerializedName("next_follow_up_on") val nextFollowUpOn: String? = null,
    @SerializedName("customer_account_id") val customerAccountId: String? = null,
    @SerializedName("created_at") val createdAt: String? = null,
)
