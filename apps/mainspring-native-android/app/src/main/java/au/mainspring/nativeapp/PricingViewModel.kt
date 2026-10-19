package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
data class PricingState(val categories: List<String> = emptyList(), val makes: List<String> = emptyList(), val category: String = "", val make: String = "",
 val rows: List<PricingRow> = emptyList(), val loading: Boolean = true, val error: String? = null)
class PricingViewModel: ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
 private val mutable = MutableStateFlow(PricingState()); val state = mutable.asStateFlow(); private var request: Job? = null
 init { viewModelScope.launch { try {
  val categories = api.pricingMeta().categories
  val makes = if("vehicle_key" in categories) api.pricingMakes() else emptyList()
  mutable.value = PricingState(categories = categories, makes = makes, category = categories.firstOrNull().orEmpty(), make = makes.firstOrNull().orEmpty(), loading = false)
  loadRows()
 } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } } } }
 fun category(value: String) { if(value !in mutable.value.categories) return; mutable.update { it.copy(category = value) }; loadRows() }
 fun make(value: String) { if(value !in mutable.value.makes) return; mutable.update { it.copy(make = value) }; loadRows() }
 fun loadRows() {
  request?.cancel(); val snapshot = mutable.value; mutable.update { it.copy(loading = true, rows = emptyList(), error = null) }
  request = viewModelScope.launch { try {
   val rows = when(snapshot.category) { "vehicle_key" -> if(snapshot.make.isBlank()) emptyList() else api.pricingKeys(snapshot.make)
    "general_service" -> api.pricingServices(); "garage_door" -> api.pricingGarage(); else -> emptyList() }
   mutable.update { it.copy(loading = false, rows = rows) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } } }
 }
}
