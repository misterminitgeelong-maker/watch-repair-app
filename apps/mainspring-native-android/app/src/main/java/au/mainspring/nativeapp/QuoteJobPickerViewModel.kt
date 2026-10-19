package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.RepairJobRead
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class QuoteJobPickerState(val loading: Boolean = false, val error: String? = null, val jobs: List<RepairJobRead> = emptyList(), val query: String = "")

/** Watch repair jobs a quote can be started for: finished jobs are left out, matches on job number, title or customer kept. */
fun quotableJobs(jobs: List<RepairJobRead>, query: String): List<RepairJobRead> {
    val term = query.trim().lowercase()
    return jobs.filter { j ->
        !isWatchCompleted(j.status) &&
            (term.isEmpty() || listOf(j.jobNumber, j.title, j.customerName, j.watchBrand, j.watchModel).any { (it ?: "").lowercase().contains(term) })
    }
}

/** Search backing the Quotes "+ New Quote" job picker; uses the same repair-jobs list endpoint as the Jobs screen. */
class QuoteJobPickerViewModel : ViewModel() {
    private val api = ApiClient.api
    private var request: Job? = null
    private val mutable = MutableStateFlow(QuoteJobPickerState())
    val state: StateFlow<QuoteJobPickerState> = mutable.asStateFlow()
    init { fetch(false) }
    fun setQuery(value: String) { mutable.update { it.copy(query = value) }; fetch(true) }
    fun refresh() = fetch(false)
    private fun fetch(debounce: Boolean) {
        request?.cancel()
        val q = mutable.value.query.trim().ifBlank { null }
        mutable.update { it.copy(loading = true, error = null) }
        request = viewModelScope.launch {
            try {
                if(debounce) delay(300)
                val rows = api.listRepairJobs(limit = 50, q = q)
                mutable.update { it.copy(loading = false, jobs = rows) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}
