package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.QuoteLineItemRead
import au.mainspring.nativeapp.api.QuoteRead
import au.mainspring.nativeapp.data.QuoteNavCache
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class QuoteDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val quote: QuoteRead? = null,
    val lines: List<QuoteLineItemRead> = emptyList(),
)

class QuoteDetailViewModel(
    private val quoteId: String,
) : ViewModel() {
    private val _state = MutableStateFlow(QuoteDetailUiState())
    val state: StateFlow<QuoteDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                var meta = QuoteNavCache[quoteId]
                if (meta == null) {
                    val page = ApiClient.api.listQuotes(limit = 500)
                    QuoteNavCache.putAll(page)
                    meta = page.firstOrNull { it.id == quoteId }
                }
                val lines = ApiClient.api.getQuoteLineItems(quoteId)
                _state.update {
                    it.copy(loading = false, quote = meta, lines = lines, error = if (meta == null) "Quote not found in recent list." else null)
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message ?: "Could not load quote") }
            }
        }
    }

    companion object {
        fun factory(quoteId: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return QuoteDetailViewModel(quoteId) as T
            }
        }
    }
}
