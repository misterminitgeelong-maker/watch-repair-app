package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName

data class StockItem(
    val id: String,
    @SerializedName("item_code") val code: String,
    @SerializedName("group_code") val group: String,
    @SerializedName("group_name") val groupName: String? = null,
    @SerializedName("item_description") val description: String? = null,
    @SerializedName("full_description") val fullDescription: String? = null,
    @SerializedName("unit_description") val unit: String? = null,
    @SerializedName("pack_description") val pack: String? = null,
    @SerializedName("pack_qty") val packQuantity: Double,
    @SerializedName("system_stock_qty") val quantity: Double,
    @SerializedName("cost_price_cents") val cost: Long,
    @SerializedName("retail_price_cents") val retail: Long,
)
data class StockPage(val items: List<StockItem>, val total: Int, val limit: Int, val offset: Int)
data class StocktakeProgress(
    @SerializedName("counted_items") val counted: Int = 0,
    @SerializedName("total_items") val total: Int = 0,
)
data class StocktakeSession(
    val id: String, val name: String, val status: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("completed_at") val completedAt: String? = null,
    val progress: StocktakeProgress? = null,
    val lines: List<StocktakeLine>? = null,
)
data class StocktakeLine(
    val id: String,
    @SerializedName("stock_item_id") val itemId: String,
    @SerializedName("item_code") val code: String,
    @SerializedName("group_code") val group: String,
    @SerializedName("full_description") val description: String? = null,
    @SerializedName("item_description") val shortDescription: String? = null,
    @SerializedName("expected_qty") val expected: Double,
    @SerializedName("system_stock_qty") val systemQuantity: Double? = null,
    @SerializedName("counted_qty") val counted: Double? = null,
    @SerializedName("variance_qty") val variance: Double? = null,
    val notes: String? = null,
)
data class StocktakeReport(
    val session: StocktakeSession,
    @SerializedName("matched_item_count") val matched: Int,
    @SerializedName("missing_item_count") val missing: Int,
    @SerializedName("over_count_item_count") val over: Int,
    @SerializedName("total_variance_qty") val varianceQuantity: Double,
    @SerializedName("total_variance_value_cents") val varianceValue: Long,
)
