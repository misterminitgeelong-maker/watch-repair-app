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
    val mode: String = "operations", val period: String = "week",
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
                else { val data = api.finance(selection.period); mutable.update { it.copy(loading = false, finance = data) } }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }

    suspend fun exportCsv(period: String, kind: String): ByteArray = withContext(Dispatchers.IO) {
        check(TokenStore.canManageInvoices()) { "Reports require an owner or manager account." }
        require(period in mobileFinancePeriods) { "Choose a valid report period." }
        require(kind == "summary" || kind == "invoices") { "Choose a valid export." }
        api.financeExport(period, kind).use { response ->
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
