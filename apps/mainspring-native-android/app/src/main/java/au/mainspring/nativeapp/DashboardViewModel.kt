package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.AutoKeyQuickIntakeCreate
import au.mainspring.nativeapp.api.DashboardWidgetsResponse
import au.mainspring.nativeapp.api.ReportsSummaryResponse
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DashboardUiState(
    val loading: Boolean = true,
    val error: String? = null,
    val summary: ReportsSummaryResponse? = null,
    val widgets: DashboardWidgetsResponse? = null,
)

class DashboardViewModel : ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val _state = MutableStateFlow(DashboardUiState())
    val state: StateFlow<DashboardUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                var summary: ReportsSummaryResponse? = null
                var widgets: DashboardWidgetsResponse? = null
                var err: String? = null
                coroutineScope {
                    val s = async {
                        try {
                            api.getReportsSummary()
                        } catch (e: Exception) {
                            err = e.userMessage()
                            null
                        }
                    }
                    val w = async {
                        try {
                            api.getReportsWidgets()
                        } catch (_: Exception) {
                            null
                        }
                    }
                    summary = s.await()
                    widgets = w.await()
                }
                _state.update {
                    it.copy(loading = false, summary = summary, widgets = widgets, error = err)
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }

}

