package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.CustomerRead
import au.mainspring.nativeapp.api.RepairJobCreate
import au.mainspring.nativeapp.api.RepairJobRead
import au.mainspring.nativeapp.api.WatchRead
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class CustomerDetailUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val customer: CustomerRead? = null,
    val watches: List<WatchRead> = emptyList(),
    val watchJobs: List<RepairJobRead> = emptyList(),
    val createJobBusy: Boolean = false,
)

class CustomerDetailViewModel(
    private val customerId: String,
) : ViewModel() {
    private val _state = MutableStateFlow(CustomerDetailUiState())
    val state: StateFlow<CustomerDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val customer = ApiClient.api.getCustomer(customerId)
                val watches: List<WatchRead>
                val jobs: List<RepairJobRead>
                coroutineScope {
                    val wDef = async {
                        try {
                            ApiClient.api.listWatches(customerId = customerId)
                        } catch (_: Exception) {
                            emptyList()
                        }
                    }
                    val jDef = async {
                        try {
                            ApiClient.api.listRepairJobs(customerId = customerId, limit = 50)
                        } catch (_: Exception) {
                            emptyList()
                        }
                    }
                    watches = wDef.await()
                    jobs = jDef.await()
                }
                _state.update {
                    it.copy(loading = false, customer = customer, watches = watches, watchJobs = jobs, error = null)
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(loading = false, error = e.message ?: "Could not load customer")
                }
            }
        }
    }

    fun createWatchRepairJob(watchId: String, title: String, description: String?, onCreated: (String) -> Unit) {
        val t = title.trim()
        if (t.isEmpty()) return
        viewModelScope.launch {
            _state.update { it.copy(createJobBusy = true, error = null) }
            try {
                val job = ApiClient.api.postRepairJob(
                    RepairJobCreate(
                        watchId = watchId,
                        title = t,
                        description = description?.trim()?.takeIf { it.isNotEmpty() },
                    ),
                )
                val jobs = try {
                    ApiClient.api.listRepairJobs(customerId = customerId, limit = 50)
                } catch (_: Exception) {
                    _state.value.watchJobs
                }
                _state.update { it.copy(createJobBusy = false, watchJobs = jobs) }
                onCreated(job.id)
            } catch (e: Exception) {
                _state.update { it.copy(createJobBusy = false, error = e.message ?: "Could not create job") }
            }
        }
    }

    companion object {
        fun factory(customerId: String): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return CustomerDetailViewModel(customerId) as T
            }
        }
    }
}
