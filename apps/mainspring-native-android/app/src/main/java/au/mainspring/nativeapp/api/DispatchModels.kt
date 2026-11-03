package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName

data class DispatchPoolJob(
    val id: String,
    @SerializedName("customer_name") val customerName: String,
    @SerializedName("job_address") val address: String,
    @SerializedName("vehicle_make") val make: String? = null,
    @SerializedName("vehicle_model") val model: String? = null,
    @SerializedName("vehicle_year") val year: String? = null,
    @SerializedName("registration_plate") val plate: String? = null,
    val description: String? = null,
    val ring: Int,
    @SerializedName("created_at") val createdAt: String,
)
data class DispatchClaim(
    @SerializedName("auto_key_job_id") val jobId: String,
    @SerializedName("job_number") val jobNumber: String,
)
