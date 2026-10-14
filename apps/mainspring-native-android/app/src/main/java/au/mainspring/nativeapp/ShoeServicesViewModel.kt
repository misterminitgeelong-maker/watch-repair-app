package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class ShoeServicesState(
    val search: String = "", val group: String = "",
    val groups: List<CatalogueGroup> = emptyList(), val items: List<CataloguePriceItem> = emptyList(),
    val combos: List<ShoeComboRule> = emptyList(), val guarantee: String? = null,
    val loading: Boolean = false, val error: String? = null,
)
class ShoeServicesViewModel : ViewModel() {
    private val api = ApiClient.service(CatalogueApi::class.java)
    private val mutable = MutableStateFlow(ShoeServicesState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }
    fun search(value: String) { mutable.update { it.copy(search = value) }; load(true) }
    fun group(value: String) { mutable.update { it.copy(group = value) }; load(false) }
    fun refresh() { load(false) }
    private fun load(debounce: Boolean) {
        request?.cancel()
        val selection = state.value
        mutable.update { it.copy(loading = true, error = null) }
        request = viewModelScope.launch {
            try {
                if(debounce) delay(300)
                val items = api.shoeItems(selection.search.trim().ifBlank { null }, selection.group.ifBlank { null })
                // Reference data loads once; combos and guarantee are non-essential so failures there never block the list.
                val groups = if(state.value.groups.isEmpty()) api.shoeGroups() else state.value.groups
                val combos = if(state.value.combos.isEmpty()) runCatching { api.shoeCombos() }.getOrDefault(emptyList()) else state.value.combos
                val guarantee = state.value.guarantee ?: runCatching { api.shoeGuarantee().shoeRepairs }.getOrNull()
                mutable.update { it.copy(loading = false, items = items, groups = groups, combos = combos, guarantee = guarantee) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}
