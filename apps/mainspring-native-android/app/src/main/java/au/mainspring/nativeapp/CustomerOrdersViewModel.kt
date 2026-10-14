package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

val CUSTOMER_ORDER_PRIORITIES = listOf("low", "normal", "high", "urgent")
val CUSTOMER_ORDER_STATUSES = listOf("to_order", "ordered", "arrived", "notified", "collected")

data class CustomerOrdersState(
    val filter: String? = null, val orders: List<CustomerOrderRead> = emptyList(),
    val loading: Boolean = false, val saving: Boolean = false, val error: String? = null,
    val customerResults: List<CustomerRead> = emptyList(), val customerSearching: Boolean = false, val customerError: String? = null,
)
class CustomerOrdersViewModel : ViewModel() {
    private val api = ApiClient.api
    private val mutable = MutableStateFlow(CustomerOrdersState())
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }
    fun filter(status: String?) { mutable.update { it.copy(filter = status) }; refresh() }
    fun refresh() {
        request?.cancel()
        val status = state.value.filter
        mutable.update { it.copy(loading = true, error = null) }
        request = viewModelScope.launch {
            try {
                val rows = api.listCustomerOrders(status)
                mutable.update { it.copy(loading = false, orders = rows) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun setStatus(order: CustomerOrderRead, status: String, onDone: () -> Unit = {}) {
        if(order.status == status) { onDone(); return }
        save({ api.updateCustomerOrder(order.id, CustomerOrderUpdate(status = status)) }, onDone)
    }
    private var customerRequest: Job? = null
    fun searchCustomers(query: String) {
        customerRequest?.cancel()
        val q = query.trim()
        if(q.isEmpty()) { mutable.update { it.copy(customerResults = emptyList(), customerSearching = false, customerError = null) }; return }
        mutable.update { it.copy(customerSearching = true, customerError = null) }
        customerRequest = viewModelScope.launch {
            try {
                delay(300)
                val rows = api.listCustomers(limit = 20, q = q)
                mutable.update { it.copy(customerSearching = false, customerResults = rows) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(customerSearching = false, customerError = e.userMessage()) } }
        }
    }
    fun clearCustomerSearch() { customerRequest?.cancel(); mutable.update { it.copy(customerResults = emptyList(), customerSearching = false, customerError = null) } }
    fun create(title: String, supplier: String, estimatedCostCents: Int, notes: String, priority: String = "normal", customerId: String? = null, onDone: () -> Unit = {}) {
        save({ api.createCustomerOrder(CustomerOrderCreate(title.trim(), supplier = supplier.trim().ifBlank { null }, customerId = customerId,
            priority = priority, estimatedCostCents = estimatedCostCents, notes = notes.trim().ifBlank { null })) }, onDone)
    }
    fun edit(order: CustomerOrderRead, title: String, supplier: String, estimatedCostCents: Int, notes: String, priority: String, onDone: () -> Unit = {}) {
        save({ api.updateCustomerOrder(order.id, CustomerOrderUpdate(title = title.trim(), supplier = supplier.trim(), priority = priority,
            estimatedCostCents = estimatedCostCents, notes = notes.trim())) }, onDone)
    }
    fun delete(order: CustomerOrderRead, onDone: () -> Unit = {}) {
        if(state.value.saving) return
        mutable.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            try {
                val response = ApiClient.service(CustomerExtrasApi::class.java).deleteCustomerOrder(order.id)
                if(!response.isSuccessful) throw retrofit2.HttpException(response)
                mutable.update { it.copy(saving = false) }; refresh(); onDone()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(saving = false, error = e.userMessage()) } }
        }
    }
    private fun save(call: suspend () -> CustomerOrderRead, onDone: () -> Unit) {
        if(state.value.saving) return
        mutable.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            try { call(); mutable.update { it.copy(saving = false) }; refresh(); onDone() }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(saving = false, error = e.userMessage()) } }
        }
    }
}
