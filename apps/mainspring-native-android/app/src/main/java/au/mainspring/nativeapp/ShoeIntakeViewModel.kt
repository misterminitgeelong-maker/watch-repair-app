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

data class ShoeIntakeState(val fields: Map<String,String> = emptyMap(), val customers: List<CustomerRead> = emptyList(),
    val catalogue: List<ShoeCatalogueItem> = emptyList(), val accounts: List<CustomerAccountRead> = emptyList(),
    val busy: Boolean = false, val error: String? = null, val complete: Boolean = false,
    val photoFailures: List<String> = emptyList())
class ShoeIntakeViewModel(private val saved: SavedStateHandle): ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
    private val gson = Gson()
    private fun restore(): Map<String,String> = try { gson.fromJson(saved.get<String>("draft") ?: drafts.loadShoeDraft() ?: "{}",
        object : TypeToken<Map<String,String>>() {}.type) ?: emptyMap() } catch(_: Exception) { emptyMap() }
    private val mutable = MutableStateFlow(ShoeIntakeState(fields = restore()))
    val state = mutable.asStateFlow()
    fun field(key: String) = mutable.value.fields[key].orEmpty()
    fun count() = field("count").toIntOrNull()?.coerceIn(1,15) ?: 1
    fun set(key: String, value: String) { val oldPhoto = if(key.endsWith(".photo")) field(key) else ""; var fields = mutable.value.fields + (key to value)
        if((key == "customerId" || key == "customerMode") && field(key) != value) fields = fields + ("accountId" to "")
        mutable.update { it.copy(fields = fields) }
        val json = gson.toJson(fields); saved["draft"] = json; drafts.saveShoeDraft(json); if(key == "uncertain") TokenStore.flushDraftCheckpoint(); if(oldPhoto.isNotBlank() && oldPhoto != value) deleteUnusedOwnedPhoto(oldPhoto) }
    fun finish() { saved["draft"] = "{}"; drafts.clearShoeDraft(); cleanupUnusedOwnedPhotos() }
    fun discard() { if(!mutable.value.busy) { finish(); mutable.update { it.copy(fields = emptyMap(), error = null, complete = false, photoFailures = emptyList()) } } }
    fun toggle(i: Int, key: String) { val keys = field("pair.$i.services").split('|').filter(String::isNotBlank).toMutableSet()
        if(!keys.add(key)) keys.remove(key); set("pair.$i.services", keys.joinToString("|")) }
    init { viewModelScope.launch {
        try { val items = api.shoeCatalogue(); mutable.update { it.copy(catalogue = items) } }
        catch(e: CancellationException) { throw e } catch(_: Exception) { mutable.update { it.copy(error = "Could not load the shoe catalogue.") } }
        try { val custom = api.customShoeServices(); mutable.update { it.copy(catalogue = (it.catalogue + custom).distinctBy { row -> row.key }) } }
        catch(e: CancellationException) { throw e }
        catch(e: Exception) { if(e !is retrofit2.HttpException || e.code() !in listOf(403,404)) mutable.update { it.copy(error = "Custom services unavailable. Verify the selected repairs before submitting.") } }
        try { val accounts = api.listCustomerAccounts(); mutable.update { it.copy(accounts = accounts) } }
        catch(e: CancellationException) { throw e } catch(_: Exception) { }
    } }
    fun search() { viewModelScope.launch {
        try { val customers = api.listCustomers(q = field("query").ifBlank { null }); mutable.update { it.copy(customers = customers) } }
        catch(e: CancellationException) { throw e } catch(_: Exception) { mutable.update { it.copy(error = "Customer search failed.") } }
    } }
    fun submit(context: Context) {
        if(mutable.value.busy) return
        mutable.update { it.copy(busy = true, error = null, complete = false, photoFailures = emptyList()) }
        viewModelScope.launch {
            try {
                                val id = createShoeIntake(mutable.value.fields.toMutableMap(), mutable.value.catalogue, object : ShoeIntakeGateway {
                    override suspend fun customer(body: CustomerCreate) = api.createCustomer(body).id
                    override suspend fun shoe(body: ShoeCreate) = api.createShoe(body).id
                    override suspend fun job(body: ShoeJobCreate): String {
                        val job = api.createShoeJob(body); trackingWarning(job.trackingSmsSkippedReason)?.let { set("trackingWarning", it) }; return job.id
                    }
                    override suspend fun link(jobId: String, shoeId: String) { api.linkShoe(jobId, ShoeLink(shoeId)) }
                    override suspend fun append(jobId: String, items: List<ShoeItemCreate>) { api.appendShoeItems(jobId, ShoeItemsAppend(items)) }
                }, ::set)
                val failures = mutableListOf<String>()
                (0 until count()).forEach { i ->
                    val key = "pair.$i.photo"; val uri = field(key)
                    if(uri.isNotBlank()) try {
                        val part = withContext(Dispatchers.IO) { photoPart(context, Uri.parse(uri)) }
                        api.uploadShoePhoto(id, part, "intake"); set(key, "")
                    } catch(e: CancellationException) { throw e }
                    catch(e: Exception) { failures.add("Pair ${i + 1}: ${e.message ?: "Photo upload failed"}") }
                }
                mutable.update { it.copy(busy = false, complete = true, photoFailures = failures) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(busy = false, error = "${e.userMessage()} Draft retained. Check shop records before retrying an unknown save.") } }
        }
    }
}



