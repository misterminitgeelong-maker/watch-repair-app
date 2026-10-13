package au.mainspring.nativeapp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
data class CustomersUiState(val loading: Boolean = false, val error: String? = null, val customers: List<CustomerRead> = emptyList(), val query: String = "", val canLoadMore: Boolean = false)
class CustomersViewModel: ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
 private val mutable = MutableStateFlow(CustomersUiState()); val state = mutable.asStateFlow(); private var request: Job? = null
 init { refresh() }
 fun setQuery(value: String) { mutable.update { it.copy(query = value) }; fetch(false, true) }
 fun refresh() { fetch(false) }
 fun loadMore() { if(mutable.value.loading || !mutable.value.canLoadMore) return; fetch(true) }
 private fun fetch(append: Boolean, debounce: Boolean = false) {
  request?.cancel(); val snapshot = mutable.value; mutable.update { it.copy(loading = true, error = null) }
  request = viewModelScope.launch { try {
   if(debounce) delay(300)
   val rows = api.listCustomers(q = snapshot.query.trim().ifBlank { null }, offset = if(append) snapshot.customers.size else 0)
   mutable.update { it.copy(loading = false, customers = if(append) (it.customers + rows).distinctBy { row -> row.id } else rows, canLoadMore = rows.size == 100) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } } }
 }
}
