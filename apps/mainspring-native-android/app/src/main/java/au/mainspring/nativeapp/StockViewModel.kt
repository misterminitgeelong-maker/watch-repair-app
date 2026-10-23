package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class StockState(
    val search: String = "", val group: String = "", val hideZero: Boolean = false,
    val items: List<StockItem> = emptyList(), val total: Int = 0,
    val loading: Boolean = false, val error: String? = null,
)
class StockViewModel : ViewModel() {
    private val api = ApiClient.api
    private val mutable = MutableStateFlow(StockState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    private var nextOffset = 0
    init { refresh() }
    fun search(value: String) { mutable.update { it.copy(search = value) }; load(false, true) }
    fun group(value: String) { mutable.update { it.copy(group = value) }; load(false, true) }
    fun hideZero(value: Boolean) { mutable.update { it.copy(hideZero = value) }; load(false) }
    fun refresh() { load(false) }
    fun more() { if(!state.value.loading && nextOffset < state.value.total) load(true) }
    private fun load(append: Boolean, debounce: Boolean = false) {
        request?.cancel()
        val selection = state.value; val offset = if(append) nextOffset else 0
        mutable.update { it.copy(loading = true, error = null, items = if(append) it.items else emptyList(), total = if(append) it.total else 0) }
        request = viewModelScope.launch {
            try {
                if(debounce) delay(300)
                val page = api.stockItems(selection.search.trim().ifBlank { null }, selection.group.trim().ifBlank { null }, selection.hideZero, offset = offset)
                nextOffset = page.offset + page.items.size
                mutable.update { it.copy(loading = false, total = page.total, items = (if(append) it.items + page.items else page.items).distinctBy { item -> item.id }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}
