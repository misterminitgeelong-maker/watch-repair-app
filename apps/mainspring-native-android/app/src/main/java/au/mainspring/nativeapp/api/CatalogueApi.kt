package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Query

data class CatalogueGroup(val id: String = "", val label: String? = null)
data class CataloguePriceItem(
    val key: String = "", val name: String = "",
    @SerializedName("price_cents") val priceCents: Int? = null,
    @SerializedName("pricing_type") val pricingType: String? = null,
    @SerializedName("group_id") val groupId: String? = null,
    @SerializedName("group_label") val groupLabel: String? = null,
    val notes: String? = null,
    @SerializedName("estimated_days_min") val daysMin: Int? = null,
    @SerializedName("estimated_days_max") val daysMax: Int? = null,
)
data class CatalogueMovement(
    val key: String = "", val name: String = "",
    @SerializedName("quote_cents") val quoteCents: Int? = null,
    @SerializedName("purchase_cost_cents") val purchaseCostCents: Int? = null,
)
/** Service quote for one movement (`GET watch-catalogue/movements/{key}/quote`). */
data class MovementQuote(@SerializedName("quote_cents") val quoteCents: Int = 0, @SerializedName("cost_cents") val costCents: Int? = null)
data class CatalogueMovements(val movements: List<CatalogueMovement> = emptyList(), val currency: String? = null,
    @SerializedName("default_margin_percent") val defaultMarginPercent: Int? = null)
data class ShoeComboRule(
    val id: String = "", val name: String = "", val discount: String? = null,
    val discounts: List<String>? = null, val rule: String? = null,
)
data class ShoeGuarantee(@SerializedName("shoe_repairs") val shoeRepairs: String? = null)

/** Read-only price-list endpoints (separate from MainspringApi; obtain via ApiClient.service). */
interface CatalogueApi {
    @GET("v1/watch-catalogue/groups") suspend fun watchGroups(): List<CatalogueGroup>
    @GET("v1/watch-catalogue/items") suspend fun watchItems(@Query("q") q: String? = null, @Query("group") group: String? = null): List<CataloguePriceItem>
    @GET("v1/watch-catalogue/movements") suspend fun watchMovements(): CatalogueMovements
    @GET("v1/watch-catalogue/movements/{key}/quote") suspend fun watchMovementQuote(@retrofit2.http.Path("key") key: String): MovementQuote
    @GET("v1/shoe-catalogue/groups") suspend fun shoeGroups(): List<CatalogueGroup>
    @GET("v1/shoe-catalogue/items") suspend fun shoeItems(@Query("q") q: String? = null, @Query("group") group: String? = null): List<CataloguePriceItem>
    @GET("v1/shoe-catalogue/combos") suspend fun shoeCombos(): List<ShoeComboRule>
    @GET("v1/shoe-catalogue/guarantee") suspend fun shoeGuarantee(): ShoeGuarantee
}
