package au.mainspring.nativeapp

import android.content.Context
import android.net.Uri
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

data class WatchIntakeState(
    val fields: Map<String, String> = emptyMap(),
    val customers: List<CustomerRead> = emptyList(),
    val watches: List<WatchRead> = emptyList(),
    val accounts: List<CustomerAccountRead> = emptyList(),
    val catalogue: List<WatchCatalogueItem> = emptyList(),
    val combos: List<WatchRepairsCombo> = emptyList(),
    val loading: Boolean = false, val busy: Boolean = false, val error: String? = null,
    val savedJobIds: List<String> = emptyList(), val complete: Boolean = false,
    val uploadFailures: List<String> = emptyList(), val progress: String? = null,
)

class WatchIntakeViewModel(private val saved: SavedStateHandle) : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
    private val gson = Gson()
    private fun restored(): Map<String, String> = try {
        gson.fromJson<Map<String, String>>(saved.get<String>("draft") ?: drafts.loadIntakeDraft() ?: "{}",
            object : TypeToken<Map<String, String>>() {}.type) ?: emptyMap()
    } catch (_: Exception) { emptyMap() }
    private val restoredFields = restored()
    private val restoredJobs = (0 until (restoredFields["watchCount"]?.toIntOrNull()?.coerceIn(1,5) ?: 1))
        .mapNotNull { restoredFields["job.$it.id"]?.takeIf(String::isNotBlank) }
    private val mutable = MutableStateFlow(WatchIntakeState(fields = restoredFields, savedJobIds = restoredJobs))
    val state = mutable.asStateFlow()
    private var searchJob: Job? = null
    fun field(key: String) = mutable.value.fields[key].orEmpty()
    fun count() = field("watchCount").toIntOrNull()?.coerceIn(1, 5) ?: 1
    fun setField(key: String, value: String) {
        val oldPhoto = if(key.startsWith("photo.")) field(key) else ""
        var fields = mutable.value.fields + (key to value)
        if((key == "customerId" || key == "customerMode") && field(key) != value) {
            fields = fields + ("accountId" to "")
            (0..4).forEach { fields = fields + ("watch.$it.id" to "") }
        }
        mutable.update { it.copy(fields = fields) }
        val json = gson.toJson(fields)
        saved["draft"] = json; drafts.saveIntakeDraft(json)
        if(key == "uncertainWrite") TokenStore.flushDraftCheckpoint()
        if(oldPhoto.isNotBlank() && oldPhoto != value) deleteUnusedOwnedPhoto(oldPhoto)
    }
    fun clearDraft() {
        if (mutable.value.busy) return
        saved["draft"] = "{}"; drafts.clearIntakeDraft()
        cleanupUnusedOwnedPhotos()
        mutable.update { it.copy(fields = emptyMap(), error = null, savedJobIds = emptyList(), complete = false, uploadFailures = emptyList()) }
    }
    fun finish() { drafts.clearIntakeDraft(); saved["draft"] = "{}"; cleanupUnusedOwnedPhotos() }
    fun photo(i: Int, side: String) = field("photo.$i.$side")
    fun setPhoto(i: Int, side: String, uri: String) = setField("photo.$i.$side", uri)
    fun changeCount(count: Int) { if (!mutable.value.busy) setField("watchCount", count.coerceIn(1,5).toString()) }
    init {
        viewModelScope.launch {
            try { val items = api.watchCatalogue(); val config = api.watchRepairsConfig()
                mutable.update { it.copy(catalogue = items, combos = config.combos) } }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { mutable.update { it.copy(error = "Price catalogue unavailable. Verify your pre-quote manually.") } }
            try { val custom = api.customWatchServices(); mutable.update { it.copy(catalogue = (it.catalogue + custom).distinctBy { row -> row.key }) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { if(e !is retrofit2.HttpException || e.code() !in listOf(403,404)) mutable.update { it.copy(error = "Custom services unavailable. Verify selected services and the pre-quote manually.") } }
            try { val accounts = api.listCustomerAccounts(); mutable.update { it.copy(accounts = accounts) } }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { /* Account billing may not be enabled on this plan. */ }
            if (field("customerId").isNotBlank()) loadWatches(field("customerId"))
        }
    }
    /** Creates a custom watch service (POST /custom-services) and selects it, like the web picker. [onDone] gets an error message or null. */
    fun addCustomService(name: String, priceCents: Int, onDone: (String?) -> Unit) {
        viewModelScope.launch {
            try {
                val item = api.createCustomWatchService(CustomServiceCreate("watch", name, priceCents))
                mutable.update { it.copy(catalogue = (it.catalogue + item).distinctBy { row -> row.key }) }
                if(item.key !in selectedServices()) toggleService(item.key)
                onDone(null)
            } catch(e: CancellationException) { throw e } catch(e: Exception) { onDone("Failed to add service. ${e.userMessage()}") }
        }
    }
    fun selectedServices() = field("services").split('|').filter(String::isNotBlank).toSet()
    fun toggleService(key: String) {
        val keys = selectedServices().toMutableSet().apply { if(!add(key)) remove(key) }
        setField("services", keys.joinToString("|"))
        val items = mutable.value.catalogue.filter { it.key in keys }
        if (items.isNotEmpty()) {
            setField("title", items.joinToString(", ") { it.name })
            setField("preQuote", java.math.BigDecimal(repairsTotal(items, mutable.value.combos)).movePointLeft(2).toPlainString())
        }
        if (items.any { it.pricingType == "quote" }) setField("status", "awaiting_quote")
    }
    fun searchCustomers(query: String) {
        if (mutable.value.busy) return
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            mutable.update { it.copy(loading = true, error = null) }
            try { val results = api.listCustomers(q = query.trim().ifBlank { null }); mutable.update { it.copy(customers = results, loading = false) } }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { mutable.update { it.copy(loading = false, error = "Could not search customers. Try again.") } }
        }
    }
    fun selectCustomer(id: String) {
        if (field("customerId") != id) { (0..4).forEach { setField("watch.$it.id", "") }; setField("accountId", "") }
        setField("customerId", id)
        viewModelScope.launch { loadWatches(id) }
    }
    private suspend fun loadWatches(id: String) {
        mutable.update { it.copy(watches = emptyList()) }
        if (id.isBlank()) return
        try { val watches = api.listWatches(customerId = id); if (field("customerId") == id) mutable.update { it.copy(watches = watches) } }
        catch (e: CancellationException) { throw e }
        catch (_: Exception) { mutable.update { it.copy(error = "Could not load watches. Select the customer again to retry.") } }
    }
    fun confirmNoUnknownRecord() { setField("uncertainWrite", ""); mutable.update { it.copy(error = null) } }
    fun submit(context: Context) {
        if (mutable.value.busy) return
        if (count() == 1 && field("quickJob") != "true" && field("skipPhotos") != "true" &&
            (photo(0, "front").isBlank() || photo(0, "back").isBlank()) && field("job.0.id").isBlank()) {
            mutable.update { it.copy(error = "Add front and back photos, or choose a quick job / skip photos.") }; return
        }
        mutable.update { it.copy(busy = true, error = null, uploadFailures = emptyList(), progress = "Saving intake…") }
        viewModelScope.launch {
            try {
                                val ids = createIntakeTickets(mutable.value.fields.toMutableMap(), object : IntakeGateway {
                    override suspend fun customer(body: CustomerCreate) = api.createCustomer(body).id
                    override suspend fun watch(body: WatchCreate) = api.createWatch(body).id
                    override suspend fun job(body: RepairJobCreate): String {
                        val job = api.postRepairJob(body)
                        trackingWarning(job.trackingSmsSkippedReason)?.let { setField("warning.${job.id}", it) }
                        setField("jobNumber.${job.id}", job.jobNumber)
                        return job.id
                    }
                }, ::setField)
                mutable.update { it.copy(savedJobIds = ids, progress = "Uploading photos…") }
                val failures = mutableListOf<String>()
                ids.forEachIndexed { i, id ->
                    listOf("front", "back").forEach { side ->
                        val uri = photo(i, side)
                        if (uri.isNotBlank()) {
                            try {
                                val part = withContext(Dispatchers.IO) { photoPart(context, Uri.parse(uri)) }
                                api.uploadPhoto(id, part, "watch_$side"); setPhoto(i, side, "")
                            } catch (e: CancellationException) { throw e }
                            catch (e: Exception) { failures.add("Watch ${i + 1}, $side: ${e.message ?: "upload failed"}") }
                        }
                    }
                }
                mutable.update { it.copy(busy = false, complete = true, uploadFailures = failures, progress = null) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) {
                val ids = (0 until count()).mapNotNull { field("job.$it.id").ifBlank { null } }
                mutable.update { it.copy(busy = false, savedJobIds = ids, progress = null,
                    error = "${e.message ?: "Could not finish intake."} Your draft is saved. Check existing records before repeating a save with an unknown result.") }
            }
        }
    }
}

internal fun photoPart(context: Context, uri: Uri): MultipartBody.Part {
    val type = context.contentResolver.getType(uri) ?: "image/jpeg"
    require(type in setOf("image/jpeg", "image/png", "image/webp")) { "Choose JPEG, PNG or WebP." }
    val bytes = preparedIntakePhoto(context, uri)
    return MultipartBody.Part.createFormData("file", "intake.jpg", bytes.toRequestBody("image/jpeg".toMediaType()))
}

