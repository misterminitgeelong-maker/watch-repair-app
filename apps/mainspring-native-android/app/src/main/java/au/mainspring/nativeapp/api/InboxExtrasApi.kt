package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

data class InboxCountRead(val count: Int = 0)

data class CardPaymentIssueRead(
    val id: String,
    @SerializedName("invoice_number") val invoiceNumber: String? = null,
    @SerializedName("amount_cents") val amountCents: Int = 0,
    val currency: String = "aud",
    val problem: String? = null,
    val status: String = "open",
    @SerializedName("can_refund") val canRefund: Boolean = false,
    @SerializedName("can_apply") val canApply: Boolean = false,
)

/** Inbox badge count, delete and card-payment resolution. Obtain via ApiClient.service(InboxExtrasApi::class.java). */
interface InboxExtrasApi {
    @GET("v1/inbox/count") suspend fun inboxCount(): InboxCountRead
    @DELETE("v1/inbox/{id}") suspend fun deleteInboxEvent(@Path("id") id: String): retrofit2.Response<Unit>
    @GET("v1/card-payment-issues/{id}") suspend fun cardPaymentIssue(@Path("id") id: String): CardPaymentIssueRead
    @POST("v1/card-payment-issues/{id}/refund") suspend fun refundCardPaymentIssue(@Path("id") id: String): CardPaymentIssueRead
    @POST("v1/card-payment-issues/{id}/apply") suspend fun applyCardPaymentIssue(@Path("id") id: String): CardPaymentIssueRead
    @POST("v1/card-payment-issues/{id}/dismiss") suspend fun dismissCardPaymentIssue(@Path("id") id: String): CardPaymentIssueRead
}
