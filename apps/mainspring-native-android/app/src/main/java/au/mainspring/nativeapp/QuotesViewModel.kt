package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.QuoteRead
import au.mainspring.nativeapp.data.QuoteNavCache
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class QuotesUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val quotes: List<QuoteRead> = emptyList(),
)

class QuotesViewModel : ViewModel() {
    private val _state = MutableStateFlow(QuotesUiState())
    val state: StateFlow<QuotesUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val list = ApiClient.api.listQuotes()
                QuoteNavCache.putAll(list)
                _state.update { it.copy(loading = false, quotes = list) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load quotes") }
            }
        }
    }
}
