package au.mainspring.nativeapp

import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class CustomerDetailUiState(
    val loading: Boolean = false, val error: String? = null, val customer: CustomerRead? = null,
    val watches: List<WatchRead> = emptyList(), val watchJobs: List<RepairJobRead> = emptyList(),
    val shoeJobs: List<ShoeRepairJobRead> = emptyList(), val mobileJobs: List<AutoKeyJobRead> = emptyList(),
    val historyErrors: Map<String,String> = emptyMap(), val more: Set<String> = emptySet(), val paging: String? = null,
    val orders: List<CustomerOrderRead> = emptyList(), val ordersLoaded: Boolean = false, val ordersError: String? = null,
    val loyalty: LoyaltyProfile? = null, val loyaltySaving: Boolean = false, val loyaltyError: String? = null,
    val mergeResults: List<CustomerRead> = emptyList(), val mergeSearching: Boolean = false, val merging: Boolean = false, val mergeError: String? = null,
    val merged: Boolean = false,
)

/** The one merge call, shared by the customer page and the Customers list "Merge duplicates" flow. */
internal suspend fun mergeCustomerRecords(primaryId: String, duplicateId: String) {
    val response = ApiClient.service(CustomerExtrasApi::class.java).mergeCustomers(CustomerMergeRequest(primaryId, duplicateId))
    if(!response.isSuccessful) throw retrofit2.HttpException(response)
}

class CustomerDetailViewModel(private val customerId: String, private val features: Set<String> = setOf("watch","shoe","auto_key")) : ViewModel() {
    private val api = ApiClient.api
    private val extras get() = ApiClient.service(CustomerExtrasApi::class.java)
    private val mutable = MutableStateFlow(CustomerDetailUiState())
    val state = mutable.asStateFlow()
    init { load() }
    private suspend fun <T> read(block: suspend () -> List<T>): Pair<List<T>, String?> = try { block() to null }
        catch(e: CancellationException) { throw e } catch(e: Exception) { emptyList<T>() to e.userMessage() }
    fun load() {
        if(mutable.value.loading || mutable.value.paging != null) return
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val customer = api.getCustomer(customerId)
                coroutineScope {
                    val watches = async { read { if("watch" in features) api.listWatches(customerId,limit = 50) else emptyList() } }
                    val watchJobs = async { read { if("watch" in features) api.listRepairJobs(customerId = customerId,limit = 50) else emptyList() } }
                    val shoes = async { read { if("shoe" in features) api.listShoeRepairJobs(customerId = customerId,limit = 50) else emptyList() } }
                    val mobile = async { read { if("auto_key" in features) api.listAutoKeyJobs(customerId = customerId,limit = 50) else emptyList() } }
                    val w = watches.await(); val j = watchJobs.await(); val s = shoes.await(); val m = mobile.await()
                    val errors = listOf("watches" to w.second, "watch" to j.second, "shoe" to s.second, "mobile" to m.second).mapNotNull { (key,error) -> error?.let { key to it } }.toMap()
                    val more = listOf("watches" to w.first.size, "watch" to j.first.size, "shoe" to s.first.size, "mobile" to m.first.size).filter { it.second == 50 }.map { it.first }.toSet()
                    mutable.update { it.copy(customer = customer, watches = w.first, watchJobs = j.first, shoeJobs = s.first, mobileJobs = m.first, historyErrors = errors, more = more, loading = false) }
                }
                loadExtras()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not refresh this customer. ${e.userMessage()}") } }
        }
    }
    /** Orders (the list endpoint has no customer filter, so it is filtered here) and loyalty load independently of the job history. */
    private fun loadExtras() {
        viewModelScope.launch {
            try {
                val rows = api.listCustomerOrders().filter { it.customerId == customerId }
                mutable.update { it.copy(orders = rows, ordersLoaded = true, ordersError = null) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(ordersError = e.userMessage()) } }
        }
        viewModelScope.launch {
            try {
                val profile = extras.loyaltyProfile(customerId)
                mutable.update { it.copy(loyalty = profile) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { /* Loyalty may be disabled for this shop or role; the panel stays hidden. */ }
        }
    }
    fun adjustLoyalty(points: Int, note: String, onDone: () -> Unit = {}) {
        if(mutable.value.loyaltySaving) return
        mutable.update { it.copy(loyaltySaving = true, loyaltyError = null) }
        viewModelScope.launch {
            try {
                val profile = extras.adjustLoyalty(customerId, LoyaltyAdjustRequest(points, note.trim()))
                mutable.update { it.copy(loyalty = profile, loyaltySaving = false) }; onDone()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loyaltySaving = false, loyaltyError = e.userMessage()) } }
        }
    }
    private var mergeSearch: Job? = null
    fun searchMergeCandidates(query: String) {
        mergeSearch?.cancel()
        val q = query.trim()
        if(q.length < 2) { mutable.update { it.copy(mergeResults = emptyList(), mergeSearching = false, mergeError = null) }; return }
        mutable.update { it.copy(mergeSearching = true, mergeError = null) }
        mergeSearch = viewModelScope.launch {
            try {
                delay(300)
                val rows = api.listCustomers(limit = 20, q = q).filter { it.id != customerId }
                mutable.update { it.copy(mergeSearching = false, mergeResults = rows) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(mergeSearching = false, mergeError = e.userMessage()) } }
        }
    }
    fun clearMerge() { mergeSearch?.cancel(); mutable.update { it.copy(mergeResults = emptyList(), mergeSearching = false, mergeError = null) } }
    /** Moves the duplicate's watches, shoes and mobile jobs onto this customer, then deletes the duplicate. */
    fun mergeDuplicate(duplicateId: String) {
        if(mutable.value.merging || duplicateId == customerId) return
        mutable.update { it.copy(merging = true, mergeError = null) }
        viewModelScope.launch {
            try {
                mergeCustomerRecords(customerId, duplicateId)
                mutable.update { it.copy(merging = false, merged = true, mergeResults = emptyList()) }
                load()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(merging = false, mergeError = e.userMessage()) } }
        }
    }
    fun mergeNoticeShown() { mutable.update { it.copy(merged = false) } }
    fun loadMore(section: String) {
        val snapshot = mutable.value
        if(snapshot.loading || snapshot.paging != null || section !in snapshot.more) return
        mutable.update { it.copy(paging = section) }
        viewModelScope.launch {
            try {
                var count = 0
                when(section) {
                    "watches" -> { val rows = api.listWatches(customerId,offset = snapshot.watches.size); count = rows.size; mutable.update { it.copy(watches = (it.watches + rows).distinctBy { row -> row.id }) } }
                    "watch" -> { val rows = api.listRepairJobs(customerId = customerId,limit = 50,offset = snapshot.watchJobs.size); count = rows.size; mutable.update { it.copy(watchJobs = (it.watchJobs + rows).distinctBy { row -> row.id }) } }
                    "shoe" -> { val rows = api.listShoeRepairJobs(customerId = customerId,limit = 50,skip = snapshot.shoeJobs.size); count = rows.size; mutable.update { it.copy(shoeJobs = (it.shoeJobs + rows).distinctBy { row -> row.id }) } }
                    "mobile" -> { val rows = api.listAutoKeyJobs(customerId = customerId,limit = 50,skip = snapshot.mobileJobs.size); count = rows.size; mutable.update { it.copy(mobileJobs = (it.mobileJobs + rows).distinctBy { row -> row.id }) } }
                }
                mutable.update { it.copy(more = if(count == 50) it.more else it.more - section, historyErrors = it.historyErrors - section) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(historyErrors = it.historyErrors + (section to e.userMessage())) } }
            finally { mutable.update { it.copy(paging = null) } }
        }
    }
    companion object { fun factory(id: String, features: Set<String> = setOf("watch","shoe","auto_key")) = object: ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = CustomerDetailViewModel(id,features) as T
    } }
}
