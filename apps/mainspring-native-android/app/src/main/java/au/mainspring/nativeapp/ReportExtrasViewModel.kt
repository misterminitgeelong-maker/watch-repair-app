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
    val customFrom: String? = null,
    val customTo: String? = null,
    val rangeError: String? = null,
    val loading: Boolean = false,
    val summary: CategorySummary? = null,
    val summaryError: String? = null,
    val gst: GstSummaryResponse? = null,
    val gstError: String? = null,
    val techs: List<TechBreakdownRow> = emptyList(),
    val techsError: String? = null,
    val trends: List<TrendMonth> = emptyList(),
    val trendsError: String? = null,
    val trendMonths: Int = 6,
    val activity: List<ActivityEvent> = emptyList(),
    val activityError: String? = null,
    val exportBusy: Boolean = false,
    val exportInfo: String? = null,
) {
    val range: ReportRange get() = ReportRange(period, customFrom, customTo)
}

/** Sales by category (with CSV export), GST, technician and trend breakdowns and the audit log; manager+ only, as on the web. */
class ReportExtrasViewModel(
    private val api: OwnerAdminApi = ApiClient.service(OwnerAdminApi::class.java),
    private val breakdown: ReportBreakdownApi = ApiClient.service(ReportBreakdownApi::class.java),
) : ViewModel() {
    private val mutable = MutableStateFlow(ReportExtrasState(allowed = TokenStore.canManageInvoices()))
    val state = mutable.asStateFlow()
    private var job: Job? = null

    init { if(state.value.allowed) refresh() }

    fun selectPeriod(period: String) {
        if(period !in ReportRange.PERIODS && period != ReportRange.CUSTOM) return
        mutable.update { it.copy(period = period, rangeError = null) }
        if(period == ReportRange.CUSTOM && (state.value.customFrom == null || state.value.customTo == null)) {
            // Wait for the picker before asking the server for a range.
            mutable.update { it.copy(summary = null, gst = null) }
            return
        }
        loadSummary()
    }

    /** Applies a custom inclusive range (civil dates, YYYY-MM-DD). Invalid ranges are reported, not sent. */
    fun setCustomRange(from: String, to: String) {
        val candidate = ReportRange(ReportRange.CUSTOM, from, to)
        val error = candidate.validate()
        mutable.update { it.copy(period = ReportRange.CUSTOM, customFrom = from, customTo = to, rangeError = error) }
        if(error == null) loadSummary()
    }

    fun selectTrendMonths(months: Int) {
        if(months !in listOf(6, 12) || months == state.value.trendMonths) return
        mutable.update { it.copy(trendMonths = months) }; loadTrends()
    }

    private fun today() = LocalDate.now(ZoneId.of(TokenStore.calendarTimezone())).toString()

    fun refresh() { loadSummary(); loadActivity(); loadTechs(); loadTrends() }

    fun loadSummary() {
        job?.cancel()
        val range = state.value.range
        val invalid = range.validate()
        if(invalid != null) { mutable.update { it.copy(rangeError = invalid, loading = false) }; return }
        val q = range.query(today())
        mutable.update { it.copy(loading = true, summaryError = null, gstError = null) }
        job = viewModelScope.launch {
            try { val s = breakdown.categorySummary(q.period, q.referenceDate, q.dateFrom, q.dateTo); mutable.update { it.copy(summary = s) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(summary = null, summaryError = e.userMessage()) } }
            try { val g = breakdown.gstSummary(q.period, q.referenceDate, q.dateFrom, q.dateTo); mutable.update { it.copy(gst = g) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(gst = null, gstError = e.userMessage()) } }
            mutable.update { it.copy(loading = false) }
        }
    }

    private fun loadTechs() {
        viewModelScope.launch {
            try { val rows = breakdown.techBreakdown(); mutable.update { it.copy(techs = rows.sortedByDescending { r -> r.totalMinutes }, techsError = null) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(techsError = e.userMessage()) } }
        }
    }

    private fun loadTrends() {
        val months = state.value.trendMonths
        viewModelScope.launch {
            try { val t = breakdown.trends(months); mutable.update { it.copy(trends = t.months, trendsError = null) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(trendsError = e.userMessage()) } }
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
        val range = state.value.range
        range.validate()?.let { throw IllegalStateException(it) }
        val q = range.query(today())
        breakdown.exportSales(category, q.period, q.referenceDate, q.dateFrom, q.dateTo).use { it.bytes() }
    }

    fun setExportBusy(busy: Boolean, info: String? = null) = mutable.update { it.copy(exportBusy = busy, exportInfo = info) }
}
