package au.mainspring.nativeapp.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH

/** Shop-level mobile services settings from the Toolkit page. Obtain via ApiClient.service(ToolkitSettingsApi::class.java). */
interface ToolkitSettingsApi {
    @GET("v1/toolkit/mobile-notifications") suspend fun notifications(): MobileNotifications
    /** Body is a JsonObject so a cleared dispatch phone is sent as an explicit null. */
    @PATCH("v1/toolkit/mobile-notifications") suspend fun saveNotifications(@Body body: JsonObject): MobileNotifications
    @GET("v1/toolkit/mobile-catalogue") suspend fun catalogue(): MobileCatalogue
    @PATCH("v1/toolkit/mobile-catalogue") suspend fun saveCatalogue(@Body body: JsonObject): MobileCatalogue
}

data class MobileNotifications(
    @SerializedName("customer_sms_enabled") val customerSmsEnabled: Boolean = true,
    @SerializedName("dispatch_phone") val dispatchPhone: String? = null,
)

data class CatalogueCategory(val key: String, val label: String = "", val description: String = "")

data class MobileCatalogue(
    @SerializedName("enabled_categories") val enabledCategories: List<String> = emptyList(),
    @SerializedName("available_categories") val availableCategories: List<CatalogueCategory> = emptyList(),
)
