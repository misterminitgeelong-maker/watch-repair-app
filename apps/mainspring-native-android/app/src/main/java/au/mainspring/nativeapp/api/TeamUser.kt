package au.mainspring.nativeapp.api
import com.google.gson.annotations.SerializedName
data class TeamUser(val id: String, @SerializedName("full_name") val name: String,
    val role: String, @SerializedName("is_active") val active: Boolean, val email: String? = null, @SerializedName("mobile_commission_rules_json") val commissionRules: String? = null)
