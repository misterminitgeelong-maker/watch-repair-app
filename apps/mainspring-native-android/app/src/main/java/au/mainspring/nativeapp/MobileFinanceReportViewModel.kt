package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

val mobileFinancePeriods = linkedMapOf(
    "week" to "This week", "last_week" to "Last week", "month" to "This month", "last_month" to "Last month",
    "quarter" to "Quarter", "last_4_weeks" to "Last 4 weeks", "last_13_weeks" to "Last 13 weeks",
)

data class MobileFinanceReportState(
    val mode: String = "operations", val period: String = "week", val customFrom: String? = null, val customTo: String? = null, val rangeError: String? = null,
    val cockpit: MobileCockpitResponse? = null, val finance: MobileFinanceResponse? = null,
    val loading: Boolean = false, val error: String? = null,
)

class MobileFinanceReportViewModel : ViewModel() {
    private val api = ApiClient.service(MobileFinanceApi::class.java)
    private val mutable = MutableStateFlow(MobileFinanceReportState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }

    fun mode(value: String) { if(value != state.value.mode) { mutable.update { it.copy(mode = value) }; refresh() } }
    /** Applies a custom inclusive date range (YYYY-MM-DD) to the finance report; invalid ranges are reported, not sent. */
    fun customRange(from: String, to: String) {
        val error = ReportRange(ReportRange.CUSTOM, from, to).validate()
        mutable.update { it.copy(period = ReportRange.CUSTOM, customFrom = from, customTo = to, rangeError = error) }
        if(error == null) refresh()
    }
    fun chooseCustom() { mutable.update { it.copy(period = ReportRange.CUSTOM, finance = null) }; if(state.value.customFrom != null && state.value.customTo != null) refresh() }
    fun period(value: String) { if(value in mobileFinancePeriods && value != state.value.period) { mutable.update { it.copy(period = value) }; refresh() } }
    fun refresh() {
        request?.cancel()
        if(!TokenStore.canManageInvoices()) {
            mutable.update { it.copy(loading = false, cockpit = null, finance = null, error = "Reports require an owner or manager account.") }; return
        }
        val selection = state.value
        mutable.update { it.copy(loading = true, error = null, cockpit = if(selection.mode == "operations") null else it.cockpit, finance = if(selection.mode == "finance") null else it.finance) }
        request = viewModelScope.launch {
            try {
                if(selection.mode == "operations") { val data = api.cockpit(); mutable.update { it.copy(loading = false, cockpit = data) } }
                else if(selection.period == ReportRange.CUSTOM) {
                    if(selection.rangeError != null || selection.customFrom == null || selection.customTo == null) { mutable.update { it.copy(loading = false) }; return@launch }
                    val data = api.finance(ReportRange.CUSTOM, selection.customFrom, selection.customTo); mutable.update { it.copy(loading = false, finance = data) }
                }
                else { val data = api.finance(selection.period); mutable.update { it.copy(loading = false, finance = data) } }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }

    suspend fun exportCsv(period: String, kind: String, dateFrom: String? = null, dateTo: String? = null): ByteArray = withContext(Dispatchers.IO) {
        check(TokenStore.canManageInvoices()) { "Reports require an owner or manager account." }
        require(period in mobileFinancePeriods || ReportRange(period, dateFrom, dateTo).let { it.custom && it.validate() == null }) { "Choose a valid report period." }
        require(kind == "summary" || kind == "invoices") { "Choose a valid export." }
        api.financeExport(period, kind, dateFrom, dateTo).use { response ->
            response.byteStream().use { input ->
                val output = java.io.ByteArrayOutputStream(); val buffer = ByteArray(8192)
                while(true) {
                    kotlin.coroutines.coroutineContext.ensureActive()
                    val count = input.read(buffer); if(count < 0) break
                    check(output.size() + count <= 2_000_000) { "The report export exceeds the supported file size." }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
        }
    }
}
