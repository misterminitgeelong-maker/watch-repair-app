package au.mainspring.nativeapp

import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class CustomerDetailUiState(
    val loading: Boolean = false, val error: String? = null, val customer: CustomerRead? = null,
    val watches: List<WatchRead> = emptyList(), val watchJobs: List<RepairJobRead> = emptyList(),
    val shoeJobs: List<ShoeRepairJobRead> = emptyList(), val mobileJobs: List<AutoKeyJobRead> = emptyList(),
    val historyErrors: Map<String,String> = emptyMap(), val more: Set<String> = emptySet(), val paging: String? = null,
)

class CustomerDetailViewModel(private val customerId: String, private val features: Set<String> = setOf("watch","shoe","auto_key")) : ViewModel() {
    private val api = ApiClient.api
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
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not refresh this customer. ${e.userMessage()}") } }
        }
    }
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
