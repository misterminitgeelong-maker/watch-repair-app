package au.mainspring.nativeapp

import com.google.gson.annotations.SerializedName

/** Body of POST /v1/custom-services (service_type is "watch" or "shoe"; the web files these under the "Custom" group). */
data class CustomServiceCreate(
    @SerializedName("service_type") val serviceType: String,
    val name: String,
    @SerializedName("price_cents") val priceCents: Int,
    @SerializedName("group_id") val groupId: String = "custom",
    @SerializedName("group_label") val groupLabel: String = "Custom",
)

/** Dollars text to cents (0 or more), or null when it is not a valid price. */
fun parseCustomServicePrice(input: String): Int? {
    val t = input.trim().removePrefix("$").replace(",", "").trim()
    if(t.isEmpty()) return null
    return try { java.math.BigDecimal(t).takeIf { it.signum() >= 0 }?.movePointRight(2)?.setScale(0, java.math.RoundingMode.HALF_UP)?.intValueExact() } catch(_: Exception) { null }
}
