package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.CustomerRead
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Customers matching [query] on name, phone or email, never including [excludeId] (the kept customer when picking the duplicate). */
fun mergeCandidates(customers: List<CustomerRead>, query: String, excludeId: String? = null): List<CustomerRead> {
    val term = query.trim().lowercase()
    val digits = term.filter { it.isDigit() }
    return customers.filter { c ->
        c.id != excludeId && (term.isEmpty() || c.fullName.lowercase().contains(term) || (c.email ?: "").lowercase().contains(term) ||
            (c.phone ?: "").lowercase().contains(term) || (digits.length >= 3 && (c.phone ?: "").filter { it.isDigit() }.contains(digits)))
    }
}

data class MergeDuplicatesState(val merging: Boolean = false, val error: String? = null, val mergedKeepName: String? = null)

/** Merge from the Customers list. Uses the same [mergeCustomerRecords] call as the customer page. */
class MergeDuplicatesViewModel : ViewModel() {
    private val mutable = MutableStateFlow(MergeDuplicatesState())
    val state: StateFlow<MergeDuplicatesState> = mutable.asStateFlow()
    fun merge(keep: CustomerRead, duplicate: CustomerRead, onDone: () -> Unit = {}) {
        if(mutable.value.merging || keep.id == duplicate.id) return
        mutable.update { it.copy(merging = true, error = null) }
        viewModelScope.launch {
            try {
                mergeCustomerRecords(keep.id, duplicate.id)
                mutable.update { it.copy(merging = false, mergedKeepName = keep.fullName) }
                onDone()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(merging = false, error = e.userMessage()) } }
        }
    }
    fun clearError() { mutable.update { it.copy(error = null) } }
    fun noticeShown() { mutable.update { it.copy(mergedKeepName = null) } }
}
