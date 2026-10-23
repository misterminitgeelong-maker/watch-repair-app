package au.mainspring.nativeapp

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.time.*
import java.time.format.*

fun scheduledTimeIso(text: String, zone: String): String? {
    if(text.isBlank()) return null
    val local = LocalDateTime.parse(text.trim(), DateTimeFormatter.ofPattern("dd/MM/uuuu HH:mm").withResolverStyle(ResolverStyle.STRICT))
    val tz = ZoneId.of(zone)
    val offsets = tz.rules.getValidOffsets(local)
    require(offsets.size == 1) { "This time is ambiguous or skipped by daylight saving. Choose another time." }
    return ZonedDateTime.ofStrict(local, offsets.single(), tz).toOffsetDateTime().toString()
}
data class MobileIntakeState(val fields: Map<String,String> = emptyMap(), val customers: List<CustomerRead> = emptyList(), val busy: Boolean = false, val error: String? = null,
    val technicians: List<TeamUser> = emptyList(), val accounts: List<CustomerAccountRead> = emptyList(), val accountsLoading: Boolean = false, val accountError: String? = null,
    val suggestion: SuggestedQuote? = null, val suggestionLoading: Boolean = false, val specMatches: List<VehicleKeySpecMatch> = emptyList(),
    val lastJob: AutoKeyJobRead? = null, val lastJobDismissed: Boolean = false, val addressSuggestions: List<String> = emptyList())
class MobileIntakeViewModel(private val saved: SavedStateHandle): ViewModel() {
    /** Replaceable so tests can run without the platform geocoder. */
    var addressSuggester: AddressSuggester = DeviceAddressSuggester
    private var suggestionJob: Job? = null; private var specJob: Job? = null; private var lastJobJob: Job? = null; private var addressJob: Job? = null
    private var suppressAddressLookup = false
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
    private val gson = Gson()
    private fun restore(): Map<String,String> = try { gson.fromJson(saved.get<String>("draft") ?: drafts.loadMobileDraft() ?: "{}", object : TypeToken<Map<String,String>>() {}.type) ?: emptyMap() } catch(_: Exception) { emptyMap() }
    private val mutable = MutableStateFlow(MobileIntakeState(fields = restore())); val state = mutable.asStateFlow()
    fun field(key: String) = mutable.value.fields[key].orEmpty()
    fun set(key: String, value: String) { var f = mutable.value.fields + (key to value)
        val changed = field(key) != value
        if((key == "customerId" || key == "customerMode") && changed) f = f + ("accountId" to "")
        mutable.update { it.copy(fields = f) }; val json = gson.toJson(f); saved["draft"] = json; drafts.saveMobileDraft(json); if(key == "uncertain") TokenStore.flushDraftCheckpoint()
        if(!changed) return
        when(key) {
            "jobType", "quantity", "extras", "accountId" -> refreshSuggestion()
            "customerId", "customerMode" -> { refreshSuggestion(); loadLastJob() }
            "make", "model", "year" -> scheduleSpecLookup()
            "address" -> if(suppressAddressLookup) suppressAddressLookup = false else scheduleAddressLookup()
        }
    }
    fun setFields(values: Map<String,String>) { values.forEach { (k, v) -> set(k, v) } }
    private fun quantityForQuote() = field("quantity").trim().toIntOrNull()?.coerceIn(1, 100) ?: 1
    /** Server tiered suggestion (GET auto-key-jobs/quote-suggestions); a local estimate stands in when the server cannot be reached. */
    fun refreshSuggestion() {
        suggestionJob?.cancel()
        val type = field("jobType").trim().ifBlank { null }; val qty = quantityForQuote(); val tier = pricingTierFor(field("accountId")); val presets = extraPresets(extras())
        suggestionJob = viewModelScope.launch {
            mutable.update { it.copy(suggestionLoading = true) }
            delay(250)
            val result = try { api.quoteSuggestions(type, qty, tier, presets.joinToString(",").ifBlank { null }).toSuggested(tier) }
            catch(e: CancellationException) { throw e }
            catch(_: Exception) { fallbackQuoteSuggestion(type, qty, tier, presets) }
            mutable.update { it.copy(suggestion = result, suggestionLoading = false) }
        }
    }
    fun extras(): List<ExtraService> = decodeExtraServices(field("extras"))
    fun setExtras(rows: List<ExtraService>) = set("extras", if(rows.isEmpty()) "" else encodeExtraServices(rows))
    /** Key-spec database search by make/model/year (GET vehicle-key-specs/search); silent on failure, as on the web. */
    fun scheduleSpecLookup() {
        specJob?.cancel()
        val make = field("make"); val model = field("model"); val year = field("year").trim().toIntOrNull()
        if(!specLookupReady(make, model)) { mutable.update { it.copy(specMatches = emptyList()) }; return }
        specJob = viewModelScope.launch {
            delay(400)
            val matches = try { api.vehicleKeySpecs(make.trim().ifBlank { null }, model.trim().ifBlank { null }, year).matches }
            catch(e: CancellationException) { throw e } catch(_: Exception) { emptyList() }
            mutable.update { it.copy(specMatches = matches) }
        }
    }
    fun applySpec(match: VehicleKeySpecMatch) { setFields(specMatchFields(mutable.value.fields, match)) }
    /** Returning customer: offer the vehicle from their latest job (web: customerLastJob banner). */
    fun loadLastJob() {
        lastJobJob?.cancel()
        val id = field("customerId")
        mutable.update { it.copy(lastJob = null, lastJobDismissed = false) }
        if(id.isBlank() || field("customerMode") == "new") return
        lastJobJob = viewModelScope.launch {
            val job = try { api.listAutoKeyJobs(limit = 1, customerId = id).firstOrNull() } catch(e: CancellationException) { throw e } catch(_: Exception) { null }
            if(field("customerId") == id) mutable.update { it.copy(lastJob = job) }
        }
    }
    fun showLastVehicle(): Boolean { val s = mutable.value; return !s.lastJobDismissed && hasLastVehicle(s.lastJob) && field("customerMode") != "new" && field("make").isBlank() && field("model").isBlank() }
    fun dismissLastVehicle() = mutable.update { it.copy(lastJobDismissed = true) }
    fun applyLastVehicle() { val job = mutable.value.lastJob ?: return
        val current = mutable.value.fields
        setFields(lastVehicleFields(job).filter { (k, _) -> k in setOf("make", "model") || current[k].orEmpty().isBlank() }); dismissLastVehicle() }
    private fun scheduleAddressLookup() {
        addressJob?.cancel()
        val query = field("address")
        if(!addressLookupReady(query)) { mutable.update { it.copy(addressSuggestions = emptyList()) }; return }
        addressJob = viewModelScope.launch {
            delay(500)
            val found = try { addressSuggester.suggest(query) } catch(e: CancellationException) { throw e } catch(_: Exception) { emptyList() }
            mutable.update { it.copy(addressSuggestions = found.filter { it != query.trim() }) }
        }
    }
    fun pickAddress(address: String) { addressJob?.cancel(); suppressAddressLookup = field("address") != address; set("address", address); mutable.update { it.copy(addressSuggestions = emptyList()) } }
    init { refreshSuggestion(); scheduleSpecLookup(); loadLastJob() }
    init { viewModelScope.launch {
        mutable.update { it.copy(accountsLoading = true) }
        try { val accounts = api.listCustomerAccounts(); mutable.update { it.copy(accounts = accounts, accountsLoading = false) } }
        catch(e: CancellationException) { throw e }
        catch(e: Exception) { mutable.update { it.copy(accountsLoading = false, accountError = if(e is retrofit2.HttpException && e.code() == 403) null else "Could not load account choices. ${e.userMessage()}") } }
    } }
    init { viewModelScope.launch {
        try {val users=api.teamUsers();mutable.update {it.copy(technicians=users)}}
        catch(e: CancellationException) {throw e} catch(_: Exception) { }
    } }
    fun finish() { saved["draft"] = "{}"; drafts.clearMobileDraft() }
    fun discard() { if(!mutable.value.busy) { finish(); mutable.update { it.copy(fields = emptyMap(), error = null, specMatches = emptyList(), lastJob = null, lastJobDismissed = false, addressSuggestions = emptyList()) }; refreshSuggestion() } }
    fun search() { viewModelScope.launch {
        try { val customers = api.listCustomers(q = field("query").ifBlank { null }); mutable.update { it.copy(customers = customers) } }
        catch(e: CancellationException) { throw e } catch(_: Exception) { mutable.update { it.copy(error = "Customer search failed.") } }
    } }
    fun submit() {
        if(mutable.value.busy || field("jobId").isNotBlank()) return
        if(!TokenStore.canWorkJobs()) { mutable.update { it.copy(error = "A technician or manager is required to create mobile jobs.") }; return }
        val fields = mutable.value.fields
        fun f(key: String) = fields[key].orEmpty().trim()
        val payload: MobileJobCreate
        val applyQuote = f("applyQuote") != "false"
        try {
            require(f("uncertain").isBlank()) { "Check shop records before retrying a save with an unknown result." }
            require(f("title").isNotBlank()) { "Enter a job title." }
            require(f("customerId").isNotBlank() || f("name").isNotBlank()) { "Select a customer or enter their name." }
            if(f("accountId").isNotBlank()) require(!mutable.value.accountsLoading && mutable.value.accounts.any { it.id == f("accountId") && it.active && f("customerId") in it.customerIds }) { "Choose a linked active account for this customer." }
            if(f("technician").isNotBlank()) require(mutable.value.technicians.any {it.id==f("technician") && it.active && it.role in listOf("tech","manager","owner")}) {"Choose an active technician."}
            val onSite = f("jobType") in MOBILE_ON_SITE_JOB_TYPES
            require(!onSite || f("address").isNotBlank()) {"Enter an address for this on-site job."}
            val quantity = f("quantity").ifBlank { "1" }.toIntOrNull() ?: error("Enter a whole key quantity.")
            require(quantity in 1..10_000) { "Key quantity must be between 1 and 10,000." }
            val year = f("year").takeIf(String::isNotBlank)?.let { it.toIntOrNull() ?: error("Enter a valid vehicle year.") }
            payload = MobileJobCreate(f("customerId"), f("title"), f("description").ifBlank { null }, f("priority").ifBlank { "normal" }, f("status").ifBlank { "awaiting_quote" },
                scheduledTimeIso(f("scheduled"), TokenStore.calendarTimezone()), f("address").ifBlank { null }, f("jobType").ifBlank { null },
                f("make").ifBlank { null }, f("model").ifBlank { null }, year, f("plate").ifBlank { null }, f("vin").ifBlank { null },
                f("keyType").ifBlank { null }, quantity, f("notes").ifBlank { null }, dollarsToCentsChecked(f("deposit")), f("bookingSms") == "true", customerAccountId = f("accountId").ifBlank { null }, assignedUserId = f("technician").ifBlank {null},
                bladeCode = f("blade").ifBlank { null }, chipType = f("chip").ifBlank { null }, salesperson = f("salesperson").ifBlank { null },
                costCents = if(applyQuote) mutable.value.suggestion?.takeIf { !it.estimated }?.totalCents else null, applySuggestedQuote = applyQuote,
                additionalServices = extraServicesPayload(extras()).ifEmpty { null }, commissionLeadSource = f("commission").ifBlank { DEFAULT_COMMISSION_SOURCE })
        } catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) }; return }
        mutable.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            try {
                var customerId = f("customerId")
                if(customerId.isBlank()) {
                    set("uncertain", "customer")
                    customerId = api.createCustomer(CustomerCreate(f("name"), f("phone").ifBlank { null }, f("email").ifBlank { null }, f("address").ifBlank { null })).id
                    set("customerId", customerId); set("hasAcknowledgement","true"); set("uncertain", "")
                }
                set("uncertain", "job")
                val job = api.createMobileJob(payload.copy(customerId = customerId))
                trackingWarning(job.trackingSmsSkippedReason)?.let { set("trackingWarning", it) }
                set("jobId", job.id); set("uncertain", ""); mutable.update { it.copy(busy = false) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                if(e is retrofit2.HttpException && e.code() in 400..499) set("uncertain", "")
                mutable.update { it.copy(busy = false, error = "Could not confirm intake. Draft retained; check shop records before retrying. ${e.userMessage()}") }
            }
        }
    }
}


