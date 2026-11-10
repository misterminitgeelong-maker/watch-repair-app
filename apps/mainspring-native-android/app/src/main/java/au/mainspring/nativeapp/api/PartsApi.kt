package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName
import retrofit2.http.*

data class PartLocation(val id: String, val name: String, val kind: String, val active: Boolean = true, val mine: Boolean = false)
data class PartModel(val id: String, val name: String, val active: Boolean = true)
data class PartLevel(@SerializedName("location_id") val locationId: String, @SerializedName("location_name") val locationName: String,
    @SerializedName("part_id") val partId: String, val sku: String, val name: String, val quantity: Int,
    @SerializedName("reorder_level") val reorderLevel: Int, val low: Boolean = false)
data class PartTransferLine(@SerializedName("part_id") val partId: String, val sku: String, val name: String,
    val quantity: Int, @SerializedName("received_quantity") val receivedQuantity: Int = 0)
data class PartTransfer(val id: String, val status: String, @SerializedName("from_location_id") val from: String,
    @SerializedName("to_location_id") val to: String, val note: String? = null,
    @SerializedName("created_at") val createdAt: String? = null, val lines: List<PartTransferLine> = emptyList())
data class PartLineInput(val sku: String, val quantity: Int)
data class PartTransferCreate(@SerializedName("from_location_id") val from: String,
    @SerializedName("to_location_id") val to: String, val lines: List<PartLineInput>, val note: String? = null)
data class PartAdjustment(@SerializedName("location_id") val location: String, val sku: String, val quantity: Int, val kind: String, val note: String? = null)
data class PurchaseRecord(val id: String, @SerializedName("purchase_ref") val reference: String,
    @SerializedName("purchase_date") val date: String? = null, val store: String? = null,
    @SerializedName("customer_name") val customer: String? = null, @SerializedName("model_name") val model: String? = null,
    val size: String? = null)
data class SuggestedPart(@SerializedName("part_id") val id: String, val sku: String, val name: String,
    val quantity: Int, @SerializedName("in_stock") val inStock: Int)
data class UsedShoePart(val id: String, @SerializedName("part_id") val partId: String,
    val sku: String, val name: String, val quantity: Int, @SerializedName("location_id") val location: String)
data class ShoePartUse(@SerializedName("part_id") val part: String, val quantity: Int,
    @SerializedName("location_id") val location: String? = null)

/** HQ catalogue-backed parts endpoints for a signed-in shop. Access remains enforced by the server. */
interface PartsApi {
    @GET("v1/stock/locations") suspend fun locations(): List<PartLocation>
    @GET("v1/stock/models") suspend fun models(): List<PartModel>
    @GET("v1/stock/levels") suspend fun levels(): List<PartLevel>
    @POST("v1/stock/adjust") suspend fun adjust(@Body body: PartAdjustment): JsonObject
    @GET("v1/stock/transfers") suspend fun transfers(): List<PartTransfer>
    @POST("v1/stock/transfers") suspend fun transfer(@Body body: PartTransferCreate): PartTransfer
    @POST("v1/stock/transfers/{id}/receive") suspend fun receive(@Path("id") id: String, @Body body: JsonObject): PartTransfer
    @GET("v1/stock/purchases/search") suspend fun purchases(@Query("q") query: String): List<PurchaseRecord>
    @GET("v1/stock/jobs/{job}/suggested-parts") suspend fun suggested(@Path("job") job: String): List<SuggestedPart>
    @GET("v1/stock/jobs/{job}/parts") suspend fun used(@Path("job") job: String): List<UsedShoePart>
    @POST("v1/stock/jobs/{job}/parts") suspend fun use(@Path("job") job: String, @Body body: ShoePartUse): UsedShoePart
}
