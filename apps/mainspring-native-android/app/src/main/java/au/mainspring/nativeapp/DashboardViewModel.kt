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
    val inboxCount: Int? = null,
    /** Number of accounts in the shop; only loaded for owners (null otherwise or on failure). */
    val teamCount: Int? = null,
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
                var inbox: Int? = null
                var err: String? = null
                var team: Int? = null
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
                    val i = async {
                        try {
                            ApiClient.service(au.mainspring.nativeapp.api.DashboardExtrasApi::class.java).getInboxCount().count
                        } catch (_: Exception) {
                            null
                        }
                    }
                    val t = async {
                        if(!TokenStore.canManageTeam()) null
                        else try { api.teamUsers().size } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (_: Exception) { null }
                    }
                    team = t.await()
                    inbox = i.await()
                    summary = s.await()
                    widgets = w.await()
                }
                _state.update {
                    it.copy(loading = false, summary = summary, widgets = widgets, inboxCount = inbox, teamCount = team, error = err)
                }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.userMessage()) }
            }
        }
    }

}

