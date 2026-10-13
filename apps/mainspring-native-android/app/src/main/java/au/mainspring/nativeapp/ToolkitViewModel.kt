package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException
import com.google.gson.Gson

data class ToolkitState(val catalog: ToolkitCatalog? = null, val selected: Set<String> = emptySet(), val saved: Set<String> = emptySet(),
 val loading: Boolean = true, val busy: Boolean = false, val error: String? = null, val readiness: ToolReadiness? = null)
class ToolkitViewModel: ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 private val mutable = MutableStateFlow(ToolkitState()); val state = mutable.asStateFlow()
 init { load() }
 fun load() { if(mutable.value.busy) return; mutable.update { it.copy(loading = true, error = null) }
  viewModelScope.launch { try {
   val catalog = api.toolkitCatalog(); val saved = api.toolkitSelection().keys.toSet()
   val raw = drafts.loadMessageDraft("toolkit")
   val draft = try { if(raw.isBlank()) null else Gson().fromJson(raw, ToolSelection::class.java).keys.toSet() } catch(_: Exception) { null }
   val valid = catalog.groups.flatMap { it.tools }.map { it.key }.toSet()
   mutable.value = ToolkitState(catalog, (draft ?: saved).intersect(valid), saved, loading = false)
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not load the shop toolkit. ${e.userMessage()}") } } }
 }
 fun toggle(key: String) { if(mutable.value.loading || mutable.value.busy) return
  mutable.update { it.copy(selected = if(key in it.selected) it.selected - key else it.selected + key, readiness = null) }; persist() }
 private fun persist() { drafts.saveMessageDraft("toolkit", Gson().toJson(ToolSelection(mutable.value.selected.toList()))) }
 fun discard() { mutable.update { it.copy(selected = it.saved, readiness = null) }; drafts.saveMessageDraft("toolkit", "") }
 fun save() { if(mutable.value.loading || mutable.value.busy) return; val keys = mutable.value.selected.toList(); mutable.update { it.copy(busy = true, error = null) }
  viewModelScope.launch { try {
   val result = api.saveToolkit(ToolSelection(keys)); drafts.saveMessageDraft("toolkit", "")
   mutable.update { it.copy(busy = false, selected = result.keys.toSet(), saved = result.keys.toSet()) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(busy = false, error = "Could not confirm selection save. Refresh before retrying. ${e.userMessage()}") } } }
 }
 fun checkScenario(id: String) { if(mutable.value.loading || mutable.value.busy) return; mutable.update { it.copy(busy = true, error = null) }
  viewModelScope.launch { try { val result = api.toolkitRecommend(ToolRecommend(id, mutable.value.selected.toList())); mutable.update { it.copy(busy = false, readiness = result) } }
   catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(busy = false, error = "Could not check this scenario. ${e.userMessage()}") } } }
 }
}

