package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class RevenueControlState(
    val queue: String = "due", val kind: String? = null,
    val items: List<RevenueItem> = emptyList(), val buckets: List<RevenueBucket> = emptyList(),
    val total: Int = 0, val warnings: List<String> = emptyList(),
    val loading: Boolean = false, val error: String? = null,
)

class RevenueControlViewModel : ViewModel() {
    private val api = ApiClient.service(RevenueApi::class.java)
    private val mutable = MutableStateFlow(RevenueControlState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    private var nextOffset = 0
    init { refresh() }
    fun queue(value: String) { mutable.update { it.copy(queue = value) }; load(false) }
    fun kind(value: String?) { mutable.update { it.copy(kind = if(it.kind == value) null else value) }; load(false) }
    fun refresh() { load(false) }
    fun more() { if(!state.value.loading && nextOffset < state.value.total) load(true) }
    private fun load(append: Boolean) {
        request?.cancel()
        val selection = state.value; val offset = if(append) nextOffset else 0
        mutable.update { it.copy(loading = true, error = null, items = if(append) it.items else emptyList()) }
        request = viewModelScope.launch {
            try {
                val page = api.revenueControl(state = selection.queue, kind = selection.kind, offset = offset)
                nextOffset = page.offset + page.items.size
                mutable.update { it.copy(loading = false, total = page.total, buckets = page.buckets, warnings = page.warnings,
                    items = (if(append) it.items + page.items else page.items).distinctBy { item -> item.key }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}
