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
