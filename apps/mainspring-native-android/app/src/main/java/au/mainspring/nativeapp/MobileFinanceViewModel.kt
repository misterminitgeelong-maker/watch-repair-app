package au.mainspring.nativeapp
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException

data class MobileFinanceState(val quotes: List<MobileQuote> = emptyList(), val invoices: List<MobileInvoice> = emptyList(),
 val loading: Boolean = false, val busy: Boolean = false, val info: String? = null, val error: String? = null,
 val unknownQuote: Boolean = false, val paymentReviewId: String? = null, val historyChecked: Boolean = false, val lastCreatedQuoteId: String? = null)
class MobileFinanceViewModel(private val jobId: String): ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
 private val operation = "mobile-quote:$jobId"
 private val paymentOperation="mobile-payment:$jobId"
 private val mutable = MutableStateFlow(MobileFinanceState(unknownQuote = drafts.pendingOperation(operation),paymentReviewId=if(drafts.pendingOperation(paymentOperation)) drafts.loadMessageDraft("$paymentOperation/request").ifBlank {"unknown"} else null))
 val state = mutable.asStateFlow()
 init { refresh() }
 fun refresh() {
  if(mutable.value.loading || mutable.value.busy) return
  mutable.update { it.copy(loading = true, error = null,historyChecked=false) }
  viewModelScope.launch { try {
   val quotes = api.mobileQuotes(jobId); val invoices = api.mobileInvoices(jobId)
   mutable.update { it.copy(loading = false, quotes = quotes, invoices = invoices, historyChecked = true) }
  } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not refresh documents. ${e.userMessage()}") } } }
 }
 fun checkedQuotes() { if(!mutable.value.historyChecked) return; drafts.setPendingOperation(operation, false); mutable.update { it.copy(unknownQuote = false) } }
 fun createQuote(lines: List<MobileQuoteLine>, gst: Boolean, inclusive: Boolean) {
  if(mutable.value.busy || mutable.value.loading || !mutable.value.historyChecked || mutable.value.unknownQuote || !TokenStore.canWorkJobs()) return
  if(lines.isEmpty() || lines.any { it.description.isBlank() || !it.quantity.isFinite() || it.quantity <= 0 || it.quantity > 10000 || it.unitCents < 0 }) {
   mutable.update { it.copy(error = "Enter a description, valid quantity and price for each line.") }; return
  }
  try { validateQuoteAmountRange(lines) } catch(e: IllegalArgumentException) { mutable.update { it.copy(error = e.userMessage()) }; return }
  if(!drafts.setPendingOperation(operation, true)) { mutable.update { it.copy(error = "Could not save the quote checkpoint. Check device storage and sign in before continuing.") }; return }
  runAction { try {
   val q = api.createMobileQuote(jobId, MobileQuoteCreate(lines, gst, inclusive))
   drafts.saveMessageDraft("quote-composer/mobile/$jobId", ""); drafts.setPendingOperation(operation, false)
   mutable.update { it.copy(quotes = listOf(q) + it.quotes, info = "Draft quote saved. Review the totals before sending.", lastCreatedQuoteId = q.id) }
  } catch(e: Exception) {
   val unknown = e !is retrofit2.HttpException || e.code() >= 500
   drafts.setPendingOperation(operation, unknown); mutable.update { it.copy(unknownQuote = unknown, historyChecked = false) }; throw e
  } }
 }
 fun sendQuote(id: String) = runAction {
  val result = api.sendMobileQuote(id)
  mutable.update { it.copy(quotes = it.quotes.map { q -> if(q.id == id) result.quote else q }, info = if(result.sent) "Quote emailed to customer." else "Quote saved, but it was not sent: ${sendFailureText(result.reason)}") }
 }
 fun createInvoice(quoteId: String) = runAction {
  try {
   val invoice = api.createMobileInvoice(jobId, quoteId)
   mutable.update { it.copy(invoices = listOf(invoice) + it.invoices, info = "Invoice created.") }
  } catch(e: Exception) {
   val invoices = api.mobileInvoices(jobId)
   mutable.update { it.copy(invoices = invoices) }
   if(invoices.none { it.quoteId == quoteId }) throw e
   mutable.update { it.copy(info = "Opened the existing invoice for this quote.") }
  }
 }
 fun sendInvoice(id: String) = runAction {
  val response = api.sendMobileInvoice(id)
  mutable.update { it.copy(info = "Invoice delivery: email ${if(response.emailSent) "sent" else "not sent"}, SMS ${if(response.smsSent) "sent" else "not sent"}.") }
 }
 fun checkedPayment() {
  if(mutable.value.loading || mutable.value.busy || !mutable.value.historyChecked) return
  drafts.saveMessageDraft("$paymentOperation/request", "")
  drafts.setPendingOperation(paymentOperation,false)
  mutable.update {it.copy(paymentReviewId=null)}
 }
 fun markPaid(id: String, method: String) {
  val snapshot=mutable.value
  if(snapshot.loading || snapshot.busy || !snapshot.historyChecked || snapshot.paymentReviewId!=null || !TokenStore.canWorkJobs()) return
  if(method !in listOf("cash","card","bank_transfer") || snapshot.invoices.none {it.id==id && it.status=="unpaid"}) return
  drafts.saveMessageDraft("$paymentOperation/request",id)
  if(!drafts.setPendingOperation(paymentOperation,true)) {mutable.update {it.copy(error="Could not save the payment checkpoint. Check device storage before continuing.")};return}
  runAction {
   try {
    val invoice = api.updateMobileInvoice(id, MobileInvoiceUpdate("paid", method))
    drafts.setPendingOperation(paymentOperation,false);drafts.saveMessageDraft("$paymentOperation/request", "")
    mutable.update { it.copy(invoices = it.invoices.map { row -> if(row.id == id) invoice else row }, info = "Invoice marked paid via ${method.replace('_', ' ')}.") }
   } catch(e: Exception) {
    val uncertain=e !is retrofit2.HttpException || e.code()>=500
    drafts.setPendingOperation(paymentOperation,uncertain)
    mutable.update {it.copy(paymentReviewId=if(uncertain) id else null,historyChecked=!uncertain)}
    throw e
   }
  }
 }
 private fun runAction(action: suspend () -> Unit) {
  if(mutable.value.busy || mutable.value.loading || !mutable.value.historyChecked || !TokenStore.canWorkJobs()) return
  mutable.update { it.copy(busy = true, error = null, info = null) }
  viewModelScope.launch { try { action() } catch(e: CancellationException) { throw e }
   catch(e: Exception) { mutable.update { it.copy(error = "Could not confirm this action. Refresh documents before repeating it. ${e.userMessage()}") } }
   finally { mutable.update { it.copy(busy = false) } } }
 }
 companion object { fun factory(jobId: String) = object: ViewModelProvider.Factory {
  @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = MobileFinanceViewModel(jobId) as T
 } }
}


/** Plain-language text for a send failure code from the backend (e.g. `no_email`). */
internal fun sendFailureText(reason: String?): String = when(reason) {
    null, "" -> "delivery failed."
    "no_email" -> "this customer has no email address."
    "no_phone" -> "this customer has no phone number."
    "email_not_configured", "email_disabled" -> "email is not set up for this shop."
    "sms_not_configured" -> "SMS is not set up for this shop."
    else -> reason.replace('_', ' ') + "."
}
