package au.mainspring.nativeapp.api

import com.google.gson.annotations.SerializedName
import retrofit2.Response
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/** Job activity timeline, duplicate, delete and the vehicle key database search used by the mobile job detail. */
interface MobileJobAdminApi {
    @GET("v1/auto-key-jobs/{id}/activity") suspend fun activity(@Path("id") id: String, @Query("limit") limit: Int = 100): List<JobActivityEvent>
    @POST("v1/auto-key-jobs/{id}/clone") suspend fun cloneJob(@Path("id") id: String): AutoKeyJobRead
    @DELETE("v1/auto-key-jobs/{id}") suspend fun deleteJob(@Path("id") id: String): Response<Unit>
    @GET("v1/vehicle-key-specs/search") suspend fun searchKeySpecs(@Query("make") make: String?, @Query("model") model: String?, @Query("year") year: Int?): KeySpecSearchResponse
}

data class JobActivityEvent(
    val id: String = "",
    @SerializedName("actor_email") val actorEmail: String? = null,
    @SerializedName("event_type") val eventType: String = "",
    @SerializedName("event_summary") val eventSummary: String = "",
    @SerializedName("created_at") val createdAt: String = "",
)

data class KeySpecSearchResponse(val matches: List<KeySpecMatch> = emptyList())

data class KeyBlank(
    @SerializedName("primary_code") val primaryCode: String? = null,
    @SerializedName("blank_reference") val blankReference: String? = null,
)

data class KeySpecMatch(
    val label: String = "",
    @SerializedName("vehicle_make") val vehicleMake: String = "",
    @SerializedName("vehicle_model") val vehicleModel: String = "",
    @SerializedName("year_from") val yearFrom: Int? = null,
    @SerializedName("year_to") val yearTo: Int? = null,
    @SerializedName("years_label") val yearsLabel: String? = null,
    @SerializedName("key_type") val keyType: String? = null,
    @SerializedName("chip_type") val chipType: String? = null,
    @SerializedName("tech_notes") val techNotes: String? = null,
    @SerializedName("key_blanks") val keyBlanks: List<KeyBlank>? = null,
    @SerializedName("suggested_blade_code") val suggestedBladeCode: String? = null,
    @SerializedName("akl_complexity") val aklComplexity: String? = null,
    @SerializedName("bsu_required") val bsuRequired: Boolean? = null,
    @SerializedName("pin_required") val pinRequired: Boolean? = null,
    @SerializedName("eeprom_required") val eepromRequired: Boolean? = null,
    @SerializedName("obd_programmable") val obdProgrammable: Boolean? = null,
    @SerializedName("dealer_required") val dealerRequired: Boolean? = null,
) {
    /** Blank codes shown under the match (first four, like the web list). */
    fun blankCodes(): List<String> = keyBlanks.orEmpty().mapNotNull { it.primaryCode?.takeIf(String::isNotBlank) ?: it.blankReference?.takeIf(String::isNotBlank) }.take(4)
        .ifEmpty { listOfNotNull(suggestedBladeCode?.takeIf(String::isNotBlank)) }
}

/** Canonical mobile status vocabulary (web `MOBILE_STATUS_OPTIONS`), in lifecycle order, with labels. */
val MOBILE_STATUS_PICKER: List<Pair<String, String>> = listOf(
    "awaiting_quote" to "Awaiting Quote", "awaiting_customer_details" to "Awaiting Customer Details", "quote_sent" to "Quote Sent",
    "awaiting_booking_confirmation" to "Awaiting Booking Confirmation", "booking_confirmed" to "Booking Confirmed", "booking_on_hold" to "Booking on Hold",
    "en_route" to "En Route", "on_site" to "On Site", "work_completed" to "Work Completed", "invoice_paid" to "Invoice Paid",
    "failed_job" to "Failed Job", "no_go" to "No Go",
)

/** Older stored statuses that present as a canonical stage (web `MOBILE_STATUS_ALIASES`). */
val MOBILE_STATUS_ALIASES: Map<String, String> = mapOf(
    "awaiting_go_ahead" to "quote_sent", "pending_booking" to "awaiting_booking_confirmation", "go_ahead" to "awaiting_booking_confirmation",
    "booked" to "booking_confirmed", "job_delayed" to "booking_on_hold", "awaiting_parts" to "booking_on_hold", "parts_to_order" to "booking_on_hold",
    "sent_to_labanda" to "booking_on_hold", "quoted_by_labanda" to "booking_on_hold", "at_third_party_for_quoting" to "booking_on_hold",
    "third_party_quote_approved" to "booking_on_hold", "at_third_party_repairer" to "booking_on_hold",
    "working_on" to "on_site", "service" to "on_site", "booking_completed" to "work_completed", "completed" to "work_completed",
    "awaiting_collection" to "work_completed", "collected" to "invoice_paid",
)
fun canonicalMobileStatus(status: String): String = MOBILE_STATUS_ALIASES[status] ?: status

val MOBILE_JOB_TYPES = listOf("Key Cutting (in-store)", "Lockout – Car", "Lockout – Boot/Trunk", "Lockout – Roadside", "All Keys Lost", "Duplicate Key", "Transponder Programming", "Remote / Fob Sync", "Ignition Repair", "Ignition Replace", "Broken Key Extraction", "Door Lock Change", "Diagnostic")
val MOBILE_PRIORITIES = listOf("low", "normal", "high", "urgent")
val MOBILE_LEAD_SOURCES = listOf("shop" to "Shop (walk-in)", "tech_sourced" to "Tech sourced", "minit_sourced" to "Minit sourced", "shop_referred" to "Shop referred")
