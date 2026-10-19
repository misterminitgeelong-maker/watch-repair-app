package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class DispatchPoolState(
    val jobs: List<DispatchPoolJob> = emptyList(),
    val loading: Boolean = false,
    val busy: Boolean = false,
    val error: String? = null,
    val unresolvedId: String = "",
    val historyChecked: Boolean = false,
    val claimed: DispatchClaim? = null,
    val polling: Boolean = false,
)

const val POOL_POLL_MS = 30_000L

class DispatchPoolViewModel : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val checkpointKey = "dispatch-claim"
    private val mutable = MutableStateFlow(DispatchPoolState(unresolvedId = drafts.loadMessageDraft(checkpointKey)))
    val state = mutable.asStateFlow()
    init { refresh() }

    fun refresh() {
        if(mutable.value.busy || mutable.value.loading) return
        mutable.update { it.copy(loading = true, historyChecked = false, error = null) }
        viewModelScope.launch {
            try {
                val jobs = api.listDispatchPool().sortedWith(compareBy<DispatchPoolJob> { it.ring }.thenBy { it.createdAt })
                mutable.update { it.copy(jobs = jobs, loading = false, historyChecked = true) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }

    /** Quiet background refresh (the web polls every 30 s). Never shows progress and keeps any visible error/claim state. */
    fun poll() {
        val now = mutable.value
        if(now.busy || now.loading || now.polling) return
        mutable.update { it.copy(polling = true) }
        viewModelScope.launch {
            try {
                val jobs = api.listDispatchPool().sortedWith(compareBy<DispatchPoolJob> { it.ring }.thenBy { it.createdAt })
                // A claim may have started while the request was in flight; its result must win.
                if(!mutable.value.busy) mutable.update { it.copy(jobs = jobs, historyChecked = true) }
            } catch(e: CancellationException) { throw e }
            catch(_: Exception) { /* silent: the next tick or a manual refresh reports problems */ }
            finally { mutable.update { it.copy(polling = false) } }
        }
    }

    fun reviewedUnresolvedClaim() {
        if(mutable.value.busy || !mutable.value.historyChecked) return
        drafts.saveMessageDraft(checkpointKey, "")
        mutable.update { it.copy(unresolvedId = "", error = null) }
    }

    fun claim(id: String) {
        val snapshot = mutable.value
        if(snapshot.busy || snapshot.loading || snapshot.claimed != null || snapshot.unresolvedId.isNotBlank()) return
        if(snapshot.jobs.none { it.id == id }) return
        drafts.saveMessageDraft(checkpointKey, id)
        try { TokenStore.flushDraftCheckpoint() }
        catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) }; return }
        mutable.update { it.copy(busy = true, error = null, unresolvedId = id, historyChecked = false) }
        viewModelScope.launch {
            try {
                val result = api.claimDispatchJob(id)
                drafts.saveMessageDraft(checkpointKey, "")
                mutable.update { it.copy(claimed = result, unresolvedId = "", jobs = it.jobs.filterNot { row -> row.id == id }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val definiteFailure = e is HttpException && e.code() in 400..499
                if(definiteFailure) drafts.saveMessageDraft(checkpointKey, "")
                mutable.update { it.copy(unresolvedId = if(definiteFailure) "" else id,
                    error = if(definiteFailure) e.userMessage() else "The claim result is unknown. Refresh the pool and check your mobile job board. ${e.userMessage()}") }
            } finally { mutable.update { it.copy(busy = false) } }
        }
    }
}
