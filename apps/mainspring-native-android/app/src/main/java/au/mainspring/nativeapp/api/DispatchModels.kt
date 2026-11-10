package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName

data class DispatchPoolJob(
    val id: String,
    @SerializedName("customer_name") val customerName: String? = null,
    @SerializedName("job_address") val address: String? = null,
    @SerializedName("job_type") val jobType: String? = null,
    val suburb: String? = null,
    val state: String? = null,
    val postcode: String? = null,
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
