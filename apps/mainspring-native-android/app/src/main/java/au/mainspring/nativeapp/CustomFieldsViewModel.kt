package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.CustomFieldsApi
import au.mainspring.nativeapp.api.CustomFieldsBody
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class CustomFieldsState(
    val fields: List<Pair<String, String>> = emptyList(),
    val loading: Boolean = true, val saving: Boolean = false, val dirty: Boolean = false,
    val error: String? = null, val info: String? = null,
)

/** Loads a job's free-form custom fields and saves the whole set back, mirroring the web JobCustomFields card. */
class CustomFieldsViewModel(private val kind: CustomFieldJobKind, private val jobId: String) : ViewModel() {
    private val api get() = ApiClient.service(CustomFieldsApi::class.java)
    private val mutable = MutableStateFlow(CustomFieldsState())
    val state = mutable.asStateFlow()
    init { load() }

    fun load() {
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val job = when(kind) { CustomFieldJobKind.Watch -> api.repairJob(jobId); CustomFieldJobKind.Shoe -> api.shoeJob(jobId); CustomFieldJobKind.Mobile -> api.autoKeyJob(jobId) }
                mutable.update { it.copy(loading = false, fields = CustomFields.fromJob(job).toList(), dirty = false) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not load custom fields. ${e.userMessage()}") } }
        }
    }

    fun setValue(name: String, value: String) = mutable.update { s -> s.copy(fields = s.fields.map { if(it.first == name) name to value else it }, dirty = true, info = null) }
    fun remove(name: String) = mutable.update { s -> s.copy(fields = s.fields.filterNot { it.first == name }, dirty = true, info = null) }

    /** Adds or overwrites a field. Returns false when the name is blank. */
    fun add(name: String, value: String): Boolean {
        val key = CustomFields.cleanName(name) ?: return false
        mutable.update { s ->
            val exists = s.fields.any { it.first == key }
            s.copy(fields = if(exists) s.fields.map { if(it.first == key) key to value else it } else s.fields + (key to value), dirty = true, info = null)
        }
        return true
    }

    fun save() {
        val s = mutable.value
        if(s.saving || s.loading) return
        mutable.update { it.copy(saving = true, error = null, info = null) }
        viewModelScope.launch {
            try {
                val body = CustomFieldsBody(s.fields.toMap(LinkedHashMap()))
                when(kind) { CustomFieldJobKind.Watch -> api.saveRepairJob(jobId, body); CustomFieldJobKind.Shoe -> api.saveShoeJob(jobId, body); CustomFieldJobKind.Mobile -> api.saveAutoKeyJob(jobId, body) }
                mutable.update { it.copy(saving = false, dirty = false, info = "Custom fields saved") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(saving = false, error = "Could not save custom fields. ${e.userMessage()}") } }
        }
    }

    companion object {
        fun factory(kind: CustomFieldJobKind, jobId: String) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST") override fun <T : ViewModel> create(modelClass: Class<T>): T = CustomFieldsViewModel(kind, jobId) as T
        }
    }
}
