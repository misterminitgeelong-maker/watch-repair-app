package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.CustomerRead
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class CustomersUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val customers: List<CustomerRead> = emptyList(),
    val query: String = "",
)

class CustomersViewModel : ViewModel() {
    private val _state = MutableStateFlow(CustomersUiState())
    val state: StateFlow<CustomersUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun setQuery(value: String) {
        _state.update { it.copy(query = value) }
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val q = _state.value.query.trim().takeIf { it.isNotEmpty() }
                val list = ApiClient.api.listCustomers(q = q)
                _state.update { it.copy(loading = false, customers = list, error = null) }
            } catch (e: Exception) {
                _state.update {
                    it.copy(loading = false, error = e.message ?: "Could not load customers")
                }
            }
        }
    }
}
