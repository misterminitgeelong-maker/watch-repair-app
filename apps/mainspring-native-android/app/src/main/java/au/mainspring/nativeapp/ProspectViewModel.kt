package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class ProspectState(val leads: List<ProspectLead> = emptyList(), val categories: List<ProspectCategory> = emptyList(), val results: List<ProspectBusiness> = emptyList(),
 val source: String? = null, val loading: Boolean = true, val busy: Boolean = false, val error: String? = null,
 val uncertainLead: String = "", val historyChecked: Boolean = false)
class ProspectViewModel: ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 private val mutable = MutableStateFlow(ProspectState(uncertainLead = drafts.loadMessageDraft("prospect-advance"))); val state = mutable.asStateFlow()
 init { refresh() }
 fun refresh() { if(mutable.value.busy) return; mutable.update { it.copy(loading = true, error = null) }
  viewModelScope.launch { try { val leads = api.prospectLeads(); val categories = api.prospectCategories().categories
   mutable.update { it.copy(loading = false, leads = leads, categories = categories, historyChecked = true) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not load prospects. ${e.userMessage()}") } } }
 }
 fun search(category: String, region: String, suburbs: String, live: Boolean) {
  if(mutable.value.busy || mutable.value.loading) return
  val areas = suburbs.split(',').map { it.trim() }.filter { it.isNotBlank() }.distinct()
  if(live && areas.size > 5) { mutable.update { it.copy(error = "Choose up to five suburbs for a fresh search.") }; return }
  runAction { val results = api.prospectSearch(category, region, areas.joinToString(",").ifBlank { null }, live)
   mutable.update { it.copy(results = results.results, source = results.source) } }
 }
 fun save(business: ProspectBusiness, region: String) = runAction {
  val lead = api.saveProspect(ProspectSave(business.name, business.address, business.phone, business.website, business.category, business.placeId, business.rating, business.reviews, region))
  mutable.update { it.copy(leads = (listOf(lead) + it.leads).distinctBy { row -> row.id }) }
 }
 fun update(id: String, name: String, email: String, notes: String, visit: String, advance: Boolean, onSaved: () -> Unit) {
  if(mutable.value.busy || mutable.value.loading || (advance && mutable.value.uncertainLead.isNotBlank())) return
  val fields = JsonObject().apply { addProperty("contact_name", name.trim()); addProperty("contact_email", email.trim()); addProperty("notes", notes.trim()) }
  try { if(visit.isBlank()) fields.add("visit_scheduled_at", JsonNull.INSTANCE) else fields.addProperty("visit_scheduled_at", scheduledTimeIso(visit, TokenStore.calendarTimezone())) }
  catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) }; return }
  if(advance) drafts.saveMessageDraft("prospect-advance", id)
  runAction { try {
   val lead = if(advance) api.advanceProspect(id, fields) else api.updateProspect(id, fields)
   drafts.saveMessageDraft("prospect-edit/$id", "")
   if(advance) drafts.saveMessageDraft("prospect-advance", "")
   mutable.update { it.copy(leads = it.leads.map { row -> if(row.id == id) lead else row }) }; onSaved()
  } catch(e: Exception) {
   if(advance) { val unknown = e !is retrofit2.HttpException || e.code() >= 500
    if(!unknown) drafts.saveMessageDraft("prospect-advance", "")
    mutable.update { it.copy(uncertainLead = if(unknown) id else "", historyChecked = false) }
   }; throw e
  } }
 }
 fun acknowledgeStage() { if(!mutable.value.historyChecked) return; drafts.saveMessageDraft("prospect-advance", ""); mutable.update { it.copy(uncertainLead = "") } }
 private fun runAction(action: suspend () -> Unit) { if(mutable.value.busy || mutable.value.loading) return
  mutable.update { it.copy(busy = true, error = null) }; viewModelScope.launch { try { action() }
   catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(error = "Could not confirm this action. Refresh and review the prospect before repeating it. ${e.userMessage()}") } }
   finally { mutable.update { it.copy(busy = false) } } }
 }
}

