package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

/** A job located on the map; [job] carries `updatedAt` for stale-write protection. */
data class LocatedStop(val job: AutoKeyJobRead, val lat: Double, val lng: Double)

data class RouteOrderState(val busy: Boolean = false, val message: String? = null, val error: String? = null, val changed: Int = 0)

/** Optimise today's driving order and persist it as `visit_order`, or clear it again (web: MobileServicesMap + visit_order). */
class RouteOrderViewModel : ViewModel() {
    private val optimiser = ApiClient.service(RouteOptimiseApi::class.java)
    private val api = ApiClient.api
    private val mutable = MutableStateFlow(RouteOrderState())
    val state = mutable.asStateFlow()

    /** [stops] must already be in appointment-time order: the first and last stay fixed. */
    fun optimise(stops: List<LocatedStop>) {
        if(mutable.value.busy) return
        if(stops.size < 2) { mutable.update { it.copy(error = "Need at least two stops with a located address to optimise.", message = null) }; return }
        mutable.update { it.copy(busy = true, error = null, message = null) }
        viewModelScope.launch {
            try {
                val order = optimiser.optimise(OptimiseRouteBody(stops.map { LatLngBody(it.lat, it.lng) })).visitOrder
                if(order.size != stops.size || order.toSet() != stops.indices.toSet()) {
                    mutable.update { it.copy(error = "The route service returned an unexpected order. Nothing was changed.") }; return@launch
                }
                writeOrders(order.mapIndexed { position, index -> stops[index].job to (position + 1) }, "Route optimised and saved")
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
            finally { mutable.update { it.copy(busy = false) } }
        }
    }

    /** Persists a manual order: [jobs] in their new stop order become visit_order 1..n (stale-write header kept per job). */
    fun saveOrder(jobs: List<AutoKeyJobRead>) {
        if(mutable.value.busy || jobs.size < 2) return
        mutable.update { it.copy(busy = true, error = null, message = null) }
        viewModelScope.launch {
            try { writeOrders(jobs.mapIndexed { i, j -> j to (i + 1) }, "Stop order saved") }
            catch(e: CancellationException) { throw e }
            finally { mutable.update { it.copy(busy = false) } }
        }
    }

    fun clear(jobs: List<AutoKeyJobRead>) {
        if(mutable.value.busy) return
        val targets = jobs.filter { it.visitOrder != null }
        if(targets.isEmpty()) { mutable.update { it.copy(message = "No saved order to clear.", error = null) }; return }
        mutable.update { it.copy(busy = true, error = null, message = null) }
        viewModelScope.launch {
            try { writeOrders(targets.map { it to null }, "Saved order cleared. Stops follow booking time") }
            catch(e: CancellationException) { throw e }
            finally { mutable.update { it.copy(busy = false) } }
        }
    }

    /** Writes sequentially; on the first failure stops and reports exactly how many were saved so the owner can refresh and re-check. */
    private suspend fun writeOrders(orders: List<Pair<AutoKeyJobRead, Int?>>, success: String) {
        var saved = 0
        for((job, order) in orders) {
            if(job.visitOrder == order) { continue }
            try {
                val body = JsonObject().apply { if(order == null) add("visit_order", JsonNull.INSTANCE) else addProperty("visit_order", order) }
                api.updateMobileJob(job.id, body, job.updatedAt)
                saved++
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                mutable.update { it.copy(changed = saved, error = "Saved $saved of ${orders.size} stops, then stopped: ${e.userMessage()} Refresh to see the current order and try again.") }
                return
            }
        }
        mutable.update { it.copy(changed = saved, message = "$success.") }
    }

    fun clearMessage() = mutable.update { it.copy(message = null, error = null) }
}
