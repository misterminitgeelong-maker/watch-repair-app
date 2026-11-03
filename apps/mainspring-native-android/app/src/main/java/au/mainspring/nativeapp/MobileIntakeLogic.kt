package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken

/** Pure helpers behind the mobile (auto key) intake, kept free of Android/Compose so they are unit tested. */

val MOBILE_JOB_TYPES = listOf("Key Cutting (in-store)", "Lockout – Car", "Lockout – Boot/Trunk", "Lockout – Roadside", "All Keys Lost", "Duplicate Key",
    "Transponder Programming", "Remote / Fob Sync", "Ignition Repair", "Ignition Replace", "Broken Key Extraction", "Door Lock Change", "Diagnostic")

/** Job types the web treats as on-site and therefore needing an address. */
val MOBILE_ON_SITE_JOB_TYPES = setOf("Lockout – Car", "Lockout – Boot/Trunk", "Lockout – Roadside", "All Keys Lost", "Remote / Fob Sync", "Ignition Repair",
    "Ignition Replace", "Broken Key Extraction", "Door Lock Change", "Diagnostic")

/** Mirrors MOBILE_COMMISSION_LEAD_SOURCE_OPTIONS in frontend lib/api/index.ts. */
val MOBILE_COMMISSION_SOURCES = listOf("shop" to "Shop (walk-in)", "tech_sourced" to "Tech sourced", "minit_sourced" to "Minit sourced", "shop_referred" to "Shop referred")
const val DEFAULT_COMMISSION_SOURCE = "shop_referred"

data class ExtraService(val preset: String = "", val custom: String = "")

private val gson = Gson()

fun encodeExtraServices(rows: List<ExtraService>): String = gson.toJson(rows)
fun decodeExtraServices(json: String): List<ExtraService> = try {
    if(json.isBlank()) emptyList() else gson.fromJson<List<ExtraService>>(json, object : TypeToken<List<ExtraService>>() {}.type).orEmpty()
        .map { ExtraService(it.preset.orEmpty(), it.custom.orEmpty()) }
} catch(_: Exception) { emptyList() }

/** Rows with neither a preset nor a custom note are dropped, as on the web. */
fun extraServicesPayload(rows: List<ExtraService>): List<AdditionalServiceDto> =
    rows.map { AdditionalServiceDto(it.preset.trim().ifBlank { null }, it.custom.trim().ifBlank { null }) }.filter { it.preset != null || it.custom != null }

fun extraPresets(rows: List<ExtraService>): List<String> = rows.map { it.preset.trim() }.filter(String::isNotEmpty)

/** A linked business account moves the quote to the B2B tier, otherwise retail (web: NewAutoKeyJobModal pricingTier). */
fun pricingTierFor(accountId: String): String = if(accountId.isNotBlank()) "b2b" else "retail"

data class SuggestedQuote(val totalCents: Int, val lines: List<QuoteSuggestionLineRead>, val tier: String, val estimated: Boolean)

fun SuggestedQuote.toUi(): String = "${if(estimated) "Estimate " else ""}$${"%d.%02d".format(totalCents / 100, totalCents % 100)}"

// Baselines from backend auto_key_quote_suggestions.py, used only when the server cannot be reached.
private val FALLBACK_BASE_CENTS = mapOf(
    "Key Cutting (in-store)" to ("Key cutting (in-store)" to 3500), "Transponder Programming" to ("Transponder programming" to 12000),
    "Lockout – Car" to ("Vehicle lockout service" to 18900), "Lockout – Boot/Trunk" to ("Boot/trunk lockout" to 18900),
    "Lockout – Roadside" to ("Roadside lockout" to 22000), "All Keys Lost" to ("All keys lost — supply & program" to 44900),
    "Remote / Fob Sync" to ("Remote / fob programming" to 9900), "Ignition Repair" to ("Ignition repair" to 15900),
    "Ignition Replace" to ("Ignition replacement" to 34900), "Duplicate Key" to ("Duplicate key — cut & program" to 8900),
    "Broken Key Extraction" to ("Broken key extraction" to 12900), "Door Lock Change" to ("Door lock service" to 19900),
    "Diagnostic" to ("Automotive key / immobiliser diagnostic" to 15900))
private val FALLBACK_TIER = mapOf("retail" to 1.0, "b2b" to 0.80, "tier1" to 0.75, "tier2" to 0.70, "tier3" to 0.65)

/** Offline stand-in for GET auto-key-jobs/quote-suggestions: same catalogue and tier multipliers, GST 10% (AUD) added to the subtotal. */
fun fallbackQuoteSuggestion(jobType: String?, quantity: Int, tier: String, presets: List<String>): SuggestedQuote {
    val qty = quantity.coerceAtLeast(1); val mult = FALLBACK_TIER[tier] ?: 1.0
    fun unit(base: Int) = Math.round(base * mult).toInt()
    val lines = mutableListOf<QuoteSuggestionLineRead>()
    val main = FALLBACK_BASE_CENTS[jobType]
    val (desc, base) = main ?: ("Mobile key service" to 15000)
    lines += QuoteSuggestionLineRead(desc, qty.toDouble(), unit(base), (qty * unit(base)))
    presets.forEach { p -> FALLBACK_BASE_CENTS[p]?.let { (d, b) -> lines += QuoteSuggestionLineRead(d, 1.0, unit(b), unit(b)) } }
    val subtotal = lines.sumOf { it.totalPriceCents }
    val tax = Math.round(subtotal * 0.10).toInt()
    return SuggestedQuote(subtotal + tax, lines, tier, estimated = true)
}

fun QuoteSuggestionRead.toSuggested(tier: String) = SuggestedQuote(totalCents, lineItems, pricingTier ?: tier, estimated = false)

/** Vehicle fields offered from a returning customer's most recent job. Only blank draft fields are filled. */
fun lastVehicleFields(job: AutoKeyJobRead): Map<String, String> = buildMap {
    job.vehicleMake?.let { put("make", it) }; job.vehicleModel?.let { put("model", it) }
    job.vehicleYear?.let { put("year", it.toString()) }
    job.registrationPlate?.let { put("plate", it) }; job.vin?.let { put("vin", it) }
    job.keyType?.let { put("keyType", it) }; job.bladeCode?.let { put("blade", it) }; job.chipType?.let { put("chip", it) }
    job.techNotes?.let { put("notes", it) }
}.filterValues(String::isNotBlank)

fun hasLastVehicle(job: AutoKeyJobRead?): Boolean = job != null && (!job.vehicleMake.isNullOrBlank() || !job.vehicleModel.isNullOrBlank())

fun lastVehicleSummary(job: AutoKeyJobRead): String =
    listOfNotNull(job.vehicleMake, job.vehicleYear?.toString(), job.vehicleModel).filter { it.isNotBlank() }.joinToString(" ") +
        (job.registrationPlate?.takeIf(String::isNotBlank)?.let { " · $it" } ?: "") + (job.keyType?.takeIf(String::isNotBlank)?.let { " · $it" } ?: "")

/** Draft fields a key-spec match fills in (web applyVehicleSpec): spec values win, blank spec values keep what is typed. */
fun specMatchFields(current: Map<String, String>, m: VehicleKeySpecMatch): Map<String, String> = buildMap {
    put("make", m.vehicleMake); put("model", m.vehicleModel)
    if(current["year"].orEmpty().isBlank() && m.yearFrom != null) put("year", m.yearFrom.toString())
    m.keyType?.takeIf(String::isNotBlank)?.let { put("keyType", it) }
    m.chipType?.takeIf(String::isNotBlank)?.let { put("chip", it) }
    m.techNotes?.takeIf(String::isNotBlank)?.let { put("notes", it) }
    m.suggestedBladeCode?.takeIf(String::isNotBlank)?.let { put("blade", it) }
}

fun specMatchSummary(m: VehicleKeySpecMatch): String = listOfNotNull(m.yearsLabel?.takeIf(String::isNotBlank), m.keyType?.takeIf(String::isNotBlank), m.chipType?.takeIf(String::isNotBlank)).joinToString(" · ")

fun specBlanks(m: VehicleKeySpecMatch): String =
    (m.keyBlanks.orEmpty().take(4).mapNotNull { it.primaryCode?.takeIf(String::isNotBlank) ?: it.blankReference?.takeIf(String::isNotBlank) }.joinToString(", ")).ifBlank { m.suggestedBladeCode.orEmpty() }

/** Whether the make/model/year typed so far is enough for the server key-spec search (web: 2+ chars of make or model). */
fun specLookupReady(make: String, model: String) = make.trim().length >= 2 || model.trim().length >= 2

/** Address suggestions are only requested for a few typed characters to avoid hammering the geocoder. */
fun addressLookupReady(text: String) = text.trim().length >= 5
