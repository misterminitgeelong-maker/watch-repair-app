package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.InboxExtrasApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Alert count for the Inbox tab badge. Call [start] while the shell is visible and [stop] when it is not;
 * it polls GET /v1/inbox/count every [intervalMs]. Failures keep the last known count.
 */
object InboxCountStore {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val _count = MutableStateFlow(0)
    val count: StateFlow<Int> = _count.asStateFlow()
    private var job: Job? = null
    var intervalMs: Long = 60_000L

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch { while (true) { refreshNow(); delay(intervalMs) } }
    }

    fun stop() { job?.cancel(); job = null }

    /** Fetch immediately (also called after deleting/resolving events). */
    suspend fun refreshNow() {
        try { _count.value = ApiClient.service(InboxExtrasApi::class.java).inboxCount().count } catch (_: Exception) {}
    }
}
