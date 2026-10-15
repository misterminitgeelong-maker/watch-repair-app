package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.time.ZoneId

data class ReportExtrasState(
    val allowed: Boolean = true,
    val period: String = "month",
    val loading: Boolean = false,
    val summary: CategorySummary? = null,
    val summaryError: String? = null,
    val activity: List<ActivityEvent> = emptyList(),
    val activityError: String? = null,
    val exportBusy: Boolean = false,
    val exportInfo: String? = null,
)

/** Sales by category (with CSV export) and the shop audit log; manager+ only, as on the web. */
class ReportExtrasViewModel(private val api: OwnerAdminApi = ApiClient.service(OwnerAdminApi::class.java)) : ViewModel() {
    private val mutable = MutableStateFlow(ReportExtrasState(allowed = TokenStore.canManageInvoices()))
    val state = mutable.asStateFlow()
    private var job: Job? = null

    init { if(state.value.allowed) refresh() }

    fun selectPeriod(period: String) {
        if(period !in listOf("day", "week", "month", "quarter")) return
        mutable.update { it.copy(period = period) }; loadSummary()
    }

    private fun today() = LocalDate.now(ZoneId.of(TokenStore.calendarTimezone())).toString()

    fun refresh() { loadSummary(); loadActivity() }

    fun loadSummary() {
        job?.cancel()
        val period = state.value.period
        mutable.update { it.copy(loading = true, summaryError = null) }
        job = viewModelScope.launch {
            try { val s = api.categorySummary(period, today()); mutable.update { it.copy(summary = s, loading = false) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, summary = null, summaryError = e.userMessage()) } }
        }
    }

    private fun loadActivity() {
        viewModelScope.launch {
            try { val rows = api.activity(50); mutable.update { it.copy(activity = rows, activityError = null) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(activityError = e.userMessage()) } }
        }
    }

    suspend fun downloadSales(category: String): ByteArray = withContext(Dispatchers.IO) {
        check(TokenStore.canManageInvoices()) { "Exports require an owner or manager account." }
        api.exportSales(category, state.value.period, today()).use { it.bytes() }
    }

    fun setExportBusy(busy: Boolean, info: String? = null) = mutable.update { it.copy(exportBusy = busy, exportInfo = info) }
}
