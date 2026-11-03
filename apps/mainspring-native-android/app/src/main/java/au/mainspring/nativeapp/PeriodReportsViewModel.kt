package au.mainspring.nativeapp

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.PeriodReport
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.ensureActive
import java.time.LocalDate
import java.time.ZoneId

data class PeriodReportsState(
    val period: String = "week", val date: String,
    val loading: Boolean = false, val current: PeriodReport? = null,
    val previous: PeriodReport? = null, val error: String? = null, val comparisonError: String? = null,
)

class PeriodReportsViewModel(private val saved: SavedStateHandle = SavedStateHandle()) : ViewModel() {
    private val api = ApiClient.api
    private val mutable = MutableStateFlow(PeriodReportsState(
        period = saved["period"] ?: "week",
        date = saved["date"] ?: LocalDate.now(ZoneId.of(TokenStore.calendarTimezone())).toString(),
    ))
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }

    fun select(period: String = state.value.period, date: String = state.value.date) {
        if(period !in listOf("day", "week", "month", "quarter") || runCatching { LocalDate.parse(date) }.isFailure) {
            mutable.update { it.copy(error = "Choose a valid report date and period.") }; return
        }
        saved["period"] = period; saved["date"] = date
        mutable.update { it.copy(period = period, date = date) }; refresh()
    }

    fun refresh() {
        request?.cancel()
        if(!TokenStore.canManageInvoices()) {
            mutable.update { it.copy(loading = false, current = null, previous = null, error = "Reports require an owner or manager account.") }; return
        }
        val selection = state.value
        mutable.update { it.copy(loading = true, current = null, previous = null, error = null, comparisonError = null) }
        request = viewModelScope.launch {
            try {
                val current = api.periodReport(selection.period, selection.date)
                mutable.update { it.copy(current = current) }
                try {
                    // The day before the server's start always belongs to the preceding calendar period.
                    val previousDate = LocalDate.parse(current.start).minusDays(1).toString()
                    val previous = api.periodReport(selection.period, previousDate)
                    mutable.update { it.copy(previous = previous) }
                } catch(e: CancellationException) { throw e }
                catch(e: Exception) { mutable.update { it.copy(comparisonError = e.userMessage()) } }
                mutable.update { it.copy(loading = false) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    suspend fun exportCsv(period: String, date: String): ByteArray = withContext(Dispatchers.IO) {
        check(TokenStore.canManageInvoices()) { "Reports require an owner or manager account." }
        require(period in listOf("day", "week", "month", "quarter")) { "Choose a valid report period." }
        LocalDate.parse(date)
        api.exportPeriodReport(period, date).use { response ->
            response.byteStream().use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while(true) {
                    kotlin.coroutines.coroutineContext.ensureActive()
                    val count = input.read(buffer)
                    if(count < 0) break
                    check(output.size() + count <= 2_000_000) { "The report export exceeds the supported file size." }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
        }
    }
}
