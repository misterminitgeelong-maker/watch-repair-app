package au.mainspring.nativeapp
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.runBlocking
import java.io.IOException
import org.junit.*
class CounterSaleWorkflowTest {
 private class Fake: CounterSaleGateway {
  var customers=0;var jobs=0;var quotes=0;var invoices=0;var completions=0;var failInvoice=false
  override suspend fun customer(body: CustomerCreate): String { customers++; return "customer-1" }
  override suspend fun job(body: MobileJobCreate): String { jobs++; return "job-1" }
  override suspend fun quote(jobId: String,body: MobileQuoteCreate): String { quotes++;return "quote-1" }
  override suspend fun invoice(jobId: String,quoteId: String): String { if(failInvoice) throw IOException("Response lost"); invoices++;return "invoice-1" }
  override suspend fun complete(jobId: String) { completions++ }
 }
 private fun request(mode: String="sale")=CounterSaleRequest("","Avery","","",null,mode,listOf(MobileQuoteLine("New key",2.0,9000)),true,true,"POS sale 07/10/2026")
 @Test fun counterSaleReusesAcknowledgedStepsAndDoesNotRecordPayment()=runBlocking {
  val fields=mutableMapOf<String,String>();val gateway=Fake();createCounterSale(request(),fields,gateway){ _,_-> }
  createCounterSale(request(),fields,gateway){ _,_-> }
  Assert.assertEquals(1,gateway.customers);Assert.assertEquals(1,gateway.jobs);Assert.assertEquals(1,gateway.quotes);Assert.assertEquals(1,gateway.invoices);Assert.assertEquals(1,gateway.completions)
  Assert.assertEquals("true",fields["done"])
 }
 @Test fun quoteOnlyDoesNotCreateInvoiceOrCompleteJob()=runBlocking {
  val gateway=Fake();createCounterSale(request("quote"),mutableMapOf(),gateway){ _,_-> }
  Assert.assertEquals(0,gateway.invoices);Assert.assertEquals(0,gateway.completions)
 }
 @Test fun unknownInvoiceResultStopsBlindRetryAndKeepsKnownJobAndQuote()=runBlocking {
  val fields=mutableMapOf<String,String>();val gateway=Fake().apply { failInvoice=true }
  try { createCounterSale(request(),fields,gateway){ _,_-> };Assert.fail("Missing transport failure") }catch(_: IOException){}
  Assert.assertEquals("invoiceId",fields["uncertain"]);Assert.assertEquals("quote-1",fields["quoteId"])
  try { createCounterSale(request(),fields,gateway){ _,_-> };Assert.fail("Unknown save retried") }catch(_: IllegalArgumentException){}
  Assert.assertEquals(1,gateway.jobs);Assert.assertEquals(1,gateway.quotes)
 }
 @Test fun linkedJobIsReusedAndNoNewJobOrCustomerIsCreated()=runBlocking {
  val fields=mutableMapOf<String,String>();val gateway=Fake()
  val linked=request().copy(customerId="c9",linkJobId="existing-job")
  val job=createCounterSale(linked,fields,gateway){ _,_-> }
  Assert.assertEquals("existing-job",job);Assert.assertEquals("existing-job",fields["jobId"])
  Assert.assertEquals(0,gateway.customers);Assert.assertEquals(0,gateway.jobs)
  Assert.assertEquals(1,gateway.quotes);Assert.assertEquals(1,gateway.invoices);Assert.assertEquals(1,gateway.completions)
 }
 @Test fun linkedQuoteOnlyAttachesQuoteToExistingJob()=runBlocking {
  val gateway=Fake();createCounterSale(request("quote").copy(customerId="c9",linkJobId="existing-job"),mutableMapOf(),gateway){ _,_-> }
  Assert.assertEquals(0,gateway.jobs);Assert.assertEquals(1,gateway.quotes);Assert.assertEquals(0,gateway.invoices)
 }
 @Test fun invalidCartNeverCreatesResources()=runBlocking {
  val gateway=Fake(); val invalid=request().copy(lines=listOf(MobileQuoteLine("",1.0,100)))
  try { createCounterSale(invalid,mutableMapOf(),gateway){ _,_-> };Assert.fail("Invalid line accepted") }catch(_: IllegalArgumentException){}
  Assert.assertEquals(0,gateway.customers);Assert.assertEquals(0,gateway.jobs)
 }
}
