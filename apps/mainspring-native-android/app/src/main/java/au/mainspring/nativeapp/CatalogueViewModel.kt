package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class CatalogueState(
    val tab: String = "repairs", val search: String = "", val group: String = "",
    val groups: List<CatalogueGroup> = emptyList(), val items: List<CataloguePriceItem> = emptyList(),
    val movements: List<CatalogueMovement> = emptyList(), val defaultMargin: Int? = null,
    val loading: Boolean = false, val error: String? = null, val movementSearch: String = "", val movementsError: String? = null,
)
class CatalogueViewModel : ViewModel() {
    private val api = ApiClient.service(CatalogueApi::class.java)
    private val mutable = MutableStateFlow(CatalogueState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }
    fun movementSearch(value: String) { mutable.update { it.copy(movementSearch = value) } }
    /** Movement database for the second catalogue card; fails quietly into [CatalogueState.movementsError]. */
    fun loadMovements() {
        viewModelScope.launch {
            try { val r = api.watchMovements(); mutable.update { it.copy(movements = r.movements, defaultMargin = r.defaultMarginPercent, movementsError = null) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(movementsError = e.userMessage()) } }
        }
    }
    fun tab(value: String) { mutable.update { it.copy(tab = value, search = "") }; load(false) }
    fun search(value: String) { mutable.update { it.copy(search = value) }; if(state.value.tab == "repairs") load(true) }
    fun group(value: String) { mutable.update { it.copy(group = value) }; load(false) }
    fun refresh() { load(false); loadMovements() }
    private fun load(debounce: Boolean) {
        request?.cancel()
        val selection = state.value
        mutable.update { it.copy(loading = true, error = null) }
        request = viewModelScope.launch {
            try {
                if(debounce) delay(300)
                if(selection.tab == "movements") {
                    val response = api.watchMovements()
                    mutable.update { it.copy(loading = false, movements = response.movements, defaultMargin = response.defaultMarginPercent) }
                } else {
                    val groups = if(state.value.groups.isEmpty()) api.watchGroups() else state.value.groups
                    val items = api.watchItems(selection.search.trim().ifBlank { null }, selection.group.ifBlank { null })
                    mutable.update { it.copy(loading = false, groups = groups, items = items) }
                }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}
