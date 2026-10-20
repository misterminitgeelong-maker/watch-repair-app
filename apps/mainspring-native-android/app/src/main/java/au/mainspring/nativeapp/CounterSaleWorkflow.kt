package au.mainspring.nativeapp
import au.mainspring.nativeapp.api.*

data class CounterSaleRequest(val customerId: String, val name: String, val phone: String, val email: String,
 val accountId: String?, val mode: String, val lines: List<MobileQuoteLine>, val gst: Boolean, val inclusive: Boolean, val title: String,
 /** Existing job to attach the sale to (web POS "Link to Job"); null creates a new job. */ val linkJobId: String? = null)
interface CounterSaleGateway {
 suspend fun customer(body: CustomerCreate): String
 suspend fun job(body: MobileJobCreate): String
 suspend fun quote(jobId: String, body: MobileQuoteCreate): String
 suspend fun invoice(jobId: String, quoteId: String): String
 suspend fun complete(jobId: String)
}
/** POS follows the existing web sequence; every acknowledged resource is retained before the next POST. */
suspend fun createCounterSale(request: CounterSaleRequest, checkpoints: MutableMap<String,String>, gateway: CounterSaleGateway,
 checkpoint: (String,String) -> Unit): String {
 require(request.mode in listOf("quote", "sale")) { "Choose quote or counter sale." }
 require(request.customerId.isNotBlank() || request.name.isNotBlank()) { "Select a customer or enter their name." }
 require(request.lines.isNotEmpty() && request.lines.size <= 30) { "Add items to the sale." }
 require(request.lines.all { it.description.isNotBlank() && it.quantity.isFinite() && it.quantity > 0 && it.quantity <= 10000 && it.unitCents in 0..100_000_000 }) { "Check each item's description, quantity and price." }
 validateQuoteAmountRange(request.lines)
 require(checkpoints["uncertain"].isNullOrBlank()) { "A previous save has an unknown result. Check the shop's records before retrying." }
 fun saved(key: String,value: String): String { checkpoints[key] = value; checkpoint(key,value); return value }
 suspend fun write(key: String, action: suspend () -> String): String {
  checkpoints[key]?.takeIf { it.isNotBlank() }?.let { return it }
  saved("uncertain", key)
  try { val id = action(); saved(key,id); saved("uncertain", ""); return id }
  catch(e: retrofit2.HttpException) { if(e.code() in 400..499) saved("uncertain", ""); throw e }
 }
 val customer = request.customerId.ifBlank { write("savedCustomerId") { gateway.customer(CustomerCreate(request.name.trim(), request.phone.trim().ifBlank { null }, request.email.trim().ifBlank { null })) } }
 val job = checkpoints["jobId"]?.takeIf { it.isNotBlank() } ?: request.linkJobId?.takeIf { it.isNotBlank() }?.let { saved("jobId", it) } ?: write("jobId") { gateway.job(MobileJobCreate(customerId = customer, title = request.title, description = request.lines.joinToString("\n") { it.description }, priority = "normal", status = "awaiting_quote",
  scheduledAt = null, address = null, jobType = null, make = null, model = null, year = null, plate = null, vin = null, keyType = null, keyQuantity = 1,
  techNotes = null, deposit = 0, customerAccountId = request.accountId)) }
 val quote = write("quoteId") { gateway.quote(job, MobileQuoteCreate(request.lines, request.gst, request.inclusive)) }
 if(request.mode == "sale") {
  write("invoiceId") { gateway.invoice(job,quote) }
  write("completed") { gateway.complete(job); "true" }
 }
 saved("done", "true")
 return job
}
