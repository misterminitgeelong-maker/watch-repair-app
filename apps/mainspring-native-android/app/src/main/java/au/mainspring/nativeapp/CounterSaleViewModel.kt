package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.time.*
import java.time.format.DateTimeFormatter

data class SaleRecoveryRecord(val id: String, val label: String)
data class CounterSaleState(val fields: Map<String,String> = emptyMap(), val customers: List<CustomerRead> = emptyList(), val accounts: List<CustomerAccountRead> = emptyList(),
 val busy: Boolean = false, val customerLoading: Boolean = false, val error: String? = null, val reviewed: Boolean = false, val recovery: List<SaleRecoveryRecord> = emptyList())
class CounterSaleViewModel: ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 private val key = "counter-sale"
 private val gson = Gson()
 private fun restored(): Map<String,String> = try { gson.fromJson(drafts.loadMessageDraft(key).ifBlank { "{}" }, object: TypeToken<Map<String,String>>(){}.type) ?: emptyMap() } catch(_: Exception) { emptyMap() }
 private val mutable = MutableStateFlow(CounterSaleState(fields = restored())); val state = mutable.asStateFlow(); private var search: Job? = null
 fun field(key: String) = mutable.value.fields[key].orEmpty()
 private fun save(key: String,value: String) { val fields = mutable.value.fields + (key to value); mutable.update { it.copy(fields = fields) }; drafts.saveMessageDraft(this.key,gson.toJson(fields)); if(key == "uncertain" || key == "done") TokenStore.flushDraftCheckpoint() }
 fun set(key: String,value: String) { if(mutable.value.busy || field("jobId").isNotBlank() || field("uncertain").isNotBlank()) return
  save(key,value); if(key == "customerId" || key == "customerMode") save("accountId", "") }
 init { searchCustomers(""); viewModelScope.launch { try { val accounts = api.listCustomerAccounts(); mutable.update { it.copy(accounts = accounts) } } catch(_: Exception) { } } }
 fun searchCustomers(query: String) { if(mutable.value.busy) return; search?.cancel(); mutable.update { it.copy(customerLoading = true) }
  search = viewModelScope.launch { try { val rows = api.listCustomers(q = query.trim().ifBlank { null }); mutable.update { it.copy(customerLoading = false, customers = rows) } }
   catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(customerLoading = false, error = e.userMessage()) } } }
 }
 fun prepare(lines: List<MobileQuoteLine>, gst: Boolean, inclusive: Boolean): CounterSaleRequest {
  val customer = if(field("customerMode") == "new") "" else field("customerId")
  require(customer.isNotBlank() || (field("customerMode") == "new" && field("name").isNotBlank())) { "Select a customer or enter the new customer's name." }
  val account = field("accountId").ifBlank { null }
  require(account == null || mutable.value.accounts.any { it.id == account && customer in it.customerIds }) { "Choose an account linked to this customer." }
  val mode = field("mode").ifBlank { "sale" }
  val date = LocalDate.now(ZoneId.of(TokenStore.calendarTimezone())).format(DateTimeFormatter.ofPattern("dd/MM/uuuu"))
  return CounterSaleRequest(customer, field("name"),field("phone"),field("email"),account,mode,lines,gst,inclusive,"${if(mode == "sale") "POS sale" else "Quote"} $date")
 }
 fun submit(request: CounterSaleRequest) {
  if(mutable.value.busy || field("done") == "true" || !TokenStore.canWorkJobs()) return
  save("request",gson.toJson(request)); execute(request)
 }
 fun resume() { if(mutable.value.busy) return; val request = try { gson.fromJson(field("request"),CounterSaleRequest::class.java) } catch(_: Exception) { null }
  if(request == null) { mutable.update { it.copy(error = "No saved checkout is available.") }; return }; execute(request) }
 private fun execute(request: CounterSaleRequest) {
  if(field("uncertain").isNotBlank()) { mutable.update { it.copy(error = "Check the saved records before continuing a checkout with an unknown result.") }; return }
  mutable.update { it.copy(busy = true,error = null) }
  viewModelScope.launch { try {
      createCounterSale(request,mutable.value.fields.toMutableMap(),object: CounterSaleGateway {
    override suspend fun customer(body: CustomerCreate) = api.createCustomer(body).id
    override suspend fun job(body: MobileJobCreate) = api.createMobileJob(body).id
    override suspend fun quote(jobId: String,body: MobileQuoteCreate) = api.createMobileQuote(jobId,body).id
    override suspend fun invoice(jobId: String,quoteId: String) = api.createMobileInvoice(jobId,quoteId).id
    override suspend fun complete(jobId: String) { api.postAutoKeyJobStatus(jobId,RepairJobStatusUpdate("work_completed")) }
   },::save)
   drafts.saveMessageDraft("quote-composer/pos", "")
   mutable.update { it.copy(busy = false) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(busy = false,reviewed = false,error = "Could not confirm checkout. Saved steps and your draft are retained. Review the shop's records before continuing. ${e.userMessage()}") } } }
 }
 fun reset() { if(mutable.value.busy || (field("uncertain").isNotBlank() && !mutable.value.reviewed)) return; drafts.saveMessageDraft(key, ""); drafts.saveMessageDraft("quote-composer/pos", ""); mutable.update { it.copy(fields = emptyMap(),error = null,reviewed = false,recovery = emptyList()) } }
 fun review() { if(mutable.value.busy) return; mutable.update { it.copy(busy = true,error = null,recovery = emptyList()) }
  viewModelScope.launch { try {
   val request = gson.fromJson(field("request"),CounterSaleRequest::class.java)
   val stage = field("uncertain")
   val rows = when(stage) {
    "savedCustomerId" -> api.listCustomers(q = request.name,limit = 200).map { SaleRecoveryRecord(it.id,"${it.fullName} · ${it.phone.orEmpty()}") }
    "jobId" -> api.mobileJobPage(query = request.title,directory = "all",limit = 200).items.filter { it.customerId == request.customerId.ifBlank { field("savedCustomerId") } }.map { SaleRecoveryRecord(it.id,"${it.jobNumber} · ${it.title} · ${it.status}") }
    "quoteId" -> api.mobileQuotes(field("jobId")).map { SaleRecoveryRecord(it.id,"${it.status} · ${au.mainspring.nativeapp.ui.formatCents(it.total,it.currency)} · ${it.lines.joinToString { line -> line.description }}") }
    "invoiceId" -> api.mobileInvoices(field("jobId")).filter { it.quoteId == field("quoteId") }.map { SaleRecoveryRecord(it.id,"${it.number} · ${it.status} · ${au.mainspring.nativeapp.ui.formatCents(it.total,it.currency)}") }
    "completed" -> listOf(api.getAutoKeyJob(field("jobId"))).filter { it.status == "work_completed" || it.status == "collected" }.map { SaleRecoveryRecord("true","Job is already ${it.status.replace('_',' ')}") }
    else -> emptyList()
   }
   mutable.update { it.copy(busy = false,reviewed = true,recovery = rows) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(busy = false,error = e.userMessage()) } } }
 }
 fun useReviewedRecord(id: String) { if(!mutable.value.reviewed || mutable.value.recovery.none { it.id == id }) return
  val stage = field("uncertain"); if(stage.isBlank()) return; save(stage,id); save("uncertain", ""); mutable.update { it.copy(reviewed = false,recovery = emptyList(),error = null) } }
 fun confirmNotSaved() { if(!mutable.value.reviewed) return; save("uncertain", ""); mutable.update { it.copy(reviewed = false,recovery = emptyList(),error = null) } }
}
