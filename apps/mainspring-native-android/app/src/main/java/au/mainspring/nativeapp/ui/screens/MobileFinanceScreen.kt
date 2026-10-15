package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.text.font.FontWeight
import au.mainspring.nativeapp.ui.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.MobileQuoteLine
import au.mainspring.nativeapp.ui.formatCents

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MobileFinanceScreen(jobId: String, onBack: () -> Unit, businessAccount: Boolean = false, onSignature: (String) -> Unit = {}, embedded: Boolean = false) {
 val vm: MobileFinanceViewModel = viewModel(key = jobId, factory = MobileFinanceViewModel.factory(jobId))
 val state by vm.state.collectAsStateWithLifecycle()
 val context = androidx.compose.ui.platform.LocalContext.current
 LaunchedEffect(jobId) {vm.refresh()}
 var printError by remember { mutableStateOf<String?>(null) }
 var composing by rememberSaveable { mutableStateOf(false) }
 LaunchedEffect(state.lastCreatedQuoteId,state.unknownQuote) { if(state.lastCreatedQuoteId != null || state.unknownQuote) composing=false }
 var confirm by remember { mutableStateOf<Pair<String, String>?>(null) }; var method by rememberSaveable { mutableStateOf("card") }
 val calibre = LocalCalibre.current
 val enabled = !state.busy && !state.loading && state.historyChecked && TokenStore.canWorkJobs()
 Scaffold(containerColor=MaterialTheme.colorScheme.background,contentWindowInsets = if(embedded) WindowInsets(0,0,0,0) else ScaffoldDefaults.contentWindowInsets, topBar = { if(!embedded) au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Mobile quotes and invoices") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
  Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
   if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
   state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }; state.info?.let { Text(it) }
   printError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
   if(state.paymentReviewId!=null) FlatPanel {
    Text("Check the payment record",style=MaterialTheme.typography.titleSmall)
    Text("A previous payment update could not be confirmed. Refresh the documents and review the invoice status.",style=MaterialTheme.typography.bodySmall)
    OutlinedButton(vm::checkedPayment,enabled=!state.loading && !state.busy && state.historyChecked) {Text("I have reviewed the payment record")}
   }
   val due=state.invoices.firstOrNull {it.status=="unpaid"}
   val draftQuote=state.quotes.firstOrNull {it.status=="draft"}
   val uninvoiced=state.quotes.firstOrNull {quote->state.invoices.none {it.quoteId==quote.id}}
   if(!state.loading && state.historyChecked) Surface(Modifier.fillMaxWidth().testTag("job-financial-next"),shape=if(calibre) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.medium,color=if(calibre) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surface) {
    Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
     SectionLabel(when {due!=null->"Payment to record";draftQuote!=null->"Ready for customer review";state.invoices.isNotEmpty() && state.invoices.all {it.status=="paid"}->"Payment recorded";else->"Quote & approval"})
     Text(when {due!=null->formatCents(due.total,due.currency);draftQuote!=null->formatCents(draftQuote.total,draftQuote.currency);state.invoices.isNotEmpty() && state.invoices.all {it.status=="paid"}->"All settled";else->"Agree the work first"},style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.Bold)
     Text(when {due!=null->"${due.number} · Record the full amount only after receiving it.";draftQuote!=null->"Review the scope and totals, then send the quote to your customer.";state.invoices.isNotEmpty() && state.invoices.all {it.status=="paid"}->"Payment is saved. You can send the invoice or save a summary below.";else->"Put the scope and price in writing. Sending a quote does not mean the customer has approved it."},style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
     when {
      state.paymentReviewId!=null -> Text("The previous payment update may have saved. Refresh and check the invoice before repeating it.",color=MaterialTheme.colorScheme.error)
      state.unknownQuote -> Text("Refresh and review saved quotes before creating another.",color=MaterialTheme.colorScheme.error)
      due!=null -> Button({confirm="paid" to due.id},enabled=enabled,modifier=Modifier.fillMaxWidth().heightIn(min=48.dp),shape=MaterialTheme.shapes.small) {Text("Record payment")}
      draftQuote!=null -> Button({confirm="quote" to draftQuote.id},enabled=enabled,modifier=Modifier.fillMaxWidth().heightIn(min=48.dp),shape=MaterialTheme.shapes.small) {Text("Send quote for review")}
      uninvoiced?.status=="approved" -> Button({confirm="invoice" to uninvoiced.id},enabled=enabled,modifier=Modifier.fillMaxWidth().heightIn(min=48.dp),shape=MaterialTheme.shapes.small) {Text("Create invoice from quote")}
      state.quotes.isNotEmpty() && state.invoices.isEmpty() -> TextButton(vm::refresh,enabled=enabled) {Text("Check customer response")}
      state.quotes.isEmpty() && state.invoices.isEmpty() -> Button({composing=true},enabled=enabled,modifier=Modifier.fillMaxWidth().heightIn(min=48.dp),shape=MaterialTheme.shapes.small) {Text("Create quote")}
     }
     if(embedded) TextButton(onBack,colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.onSurfaceVariant)) {Text("Back to job overview")}
    }
   }
   Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
    TextButton(onClick=vm::refresh,enabled=!state.loading && !state.busy,colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.onSurfaceVariant)) { Text("Refresh") }
    if(!state.unknownQuote && (state.quotes.isNotEmpty() || state.invoices.isNotEmpty())) TextButton({composing=true},enabled=enabled,colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.onSurfaceVariant)) {Text("Create quote")}
   }
   au.mainspring.nativeapp.ui.SectionLabel("Quotes")
   if(state.quotes.isEmpty() && !state.loading) Text("No quotes yet.",style=MaterialTheme.typography.bodySmall)
   state.quotes.forEach { q -> Surface(Modifier.fillMaxWidth(),shape=if(calibre) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.medium,color=if(calibre) androidx.compose.ui.graphics.Color.Transparent else MaterialTheme.colorScheme.surface) { Column(Modifier.padding(if(calibre) PaddingValues(vertical=14.dp) else PaddingValues(16.dp)), verticalArrangement = Arrangement.spacedBy(10.dp)) {
    if(calibre) HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {StatusPill(q.status);Text(formatCents(q.total,q.currency),style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.SemiBold)}
    Text("Subtotal ${formatCents(q.subtotal, q.currency)} · GST ${formatCents(q.tax, q.currency)}",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
    q.lines.forEach { Text("${it.description}: ${java.math.BigDecimal.valueOf(it.quantity).stripTrailingZeros().toPlainString()} × ${formatCents(it.unitCents, q.currency)}") }
    q.signer?.let { Text("Signed by $it") }
    q.signedAt?.let { Text("Signed ${au.mainspring.nativeapp.ui.formatShopDate(it)}") }
    if(q.hasSignature) OutlinedButton({ onSignature(q.id) }, enabled = !state.loading && !state.busy && TokenStore.canWorkJobs()) { Text("View customer signature") }
    if(q.status == "draft") OutlinedButton(onClick = { confirm = "quote" to q.id }, enabled = enabled) { Text("Send quote") }
    if(state.invoices.none { it.quoteId == q.id }) OutlinedButton(onClick = { confirm = "invoice" to q.id }, enabled = enabled) { Text("Create invoice") }
   } } }
   au.mainspring.nativeapp.ui.SectionLabel("Invoices")
   if(state.invoices.isEmpty() && !state.loading) Text("No invoices yet.",style=MaterialTheme.typography.bodySmall)
   state.invoices.forEach { invoice -> Surface(Modifier.fillMaxWidth(),shape=if(calibre) androidx.compose.ui.graphics.RectangleShape else MaterialTheme.shapes.medium,color=if(calibre) androidx.compose.ui.graphics.Color.Transparent else MaterialTheme.colorScheme.surface) { Column(Modifier.padding(if(calibre) PaddingValues(vertical=14.dp) else PaddingValues(16.dp)), verticalArrangement = Arrangement.spacedBy(10.dp)) {
    if(calibre) HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {Text(invoice.number,style=MaterialTheme.typography.titleSmall);StatusPill(invoice.status)}
    Text(formatCents(invoice.total,invoice.currency),style=MaterialTheme.typography.titleLarge)
    invoice.paymentMethod?.let { Text("Payment: ${au.mainspring.nativeapp.ui.statusLabel(it)}") }
    OutlinedButton(onClick = { try {
     printInvoiceSummary(context,InvoiceSummary(invoice.number,invoice.status,
      details = listOfNotNull(invoice.customerName?.let { "Customer: $it" },invoice.jobNumber?.let { "Job: $it" },invoice.createdAt?.let { "Created ${au.mainspring.nativeapp.ui.formatShopDate(it)}" },invoice.paymentMethod?.let { "Payment method: ${au.mainspring.nativeapp.ui.statusLabel(it)}" }),
      totals = listOfNotNull(invoice.subtotal?.let { "Subtotal" to formatCents(it,invoice.currency) },invoice.tax?.let { "Tax / GST" to formatCents(it,invoice.currency) },"Total" to formatCents(invoice.total,invoice.currency))))
    } catch(e: Exception) { printError = e.userMessage() } },enabled = !state.loading && !state.busy) { Text("Print / save invoice summary") }
    OutlinedButton(onClick = { confirm = "sendInvoice" to invoice.id }, enabled = enabled) { Text("Send invoice") }
    if(invoice.status == "unpaid") OutlinedButton(onClick = { confirm = "paid" to invoice.id }, enabled = enabled && state.paymentReviewId==null) { Text("Mark paid") }
   } } }
   if(state.unknownQuote) OutlinedButton(onClick = vm::checkedQuotes, enabled = enabled && state.historyChecked) { Text("I checked for the saved quote") }

  }
 }
 if(composing) ModalBottomSheet(onDismissRequest={if(!state.busy) composing=false},sheetState=rememberModalBottomSheetState(skipPartiallyExpanded=true)) {
  Column(Modifier.fillMaxWidth().fillMaxHeight(0.94f).testTag("quote-editor").imePadding(),verticalArrangement=Arrangement.spacedBy(10.dp)) {
   Row(Modifier.fillMaxWidth().padding(horizontal=16.dp),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=androidx.compose.ui.Alignment.CenterVertically) {
    Text("New quote",style=MaterialTheme.typography.titleLarge)
    TextButton({composing=false},enabled=!state.busy) {Text("Close")}
   }
   state.error?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)}
   if(state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
   QuoteComposer("quote-composer/mobile/$jobId",businessAccount,enabled,catalogue=true,currency=state.quotes.firstOrNull()?.currency ?: state.invoices.firstOrNull()?.currency ?: TokenStore.shopValue("currency"),resetVersion=state.lastCreatedQuoteId,modifier=Modifier.weight(1f),sheetLayout=true,onSave=vm::createQuote)
  }
 }
 confirm?.takeIf {it.first=="paid"}?.let {action->
  val invoice=state.invoices.firstOrNull {it.id==action.second}
  ModalBottomSheet(onDismissRequest={confirm=null},sheetState=rememberModalBottomSheetState(skipPartiallyExpanded=true)) {
   Column(Modifier.fillMaxWidth().testTag("payment-sheet").padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
    SectionLabel("Payment received")
    Text("Record payment",style=MaterialTheme.typography.titleLarge)
    invoice?.let {Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {Text(it.number);Text(formatCents(it.total,it.currency),style=MaterialTheme.typography.titleLarge)}}
    Text("Record this only after receiving the full invoice amount.",style=MaterialTheme.typography.bodySmall)
    Column {listOf("card","cash","bank_transfer").forEach {option->Row(Modifier.fillMaxWidth(),verticalAlignment=androidx.compose.ui.Alignment.CenterVertically) {RadioButton(method==option,{method=option},enabled=enabled);Text(au.mainspring.nativeapp.ui.statusLabel(option).replaceFirstChar {it.uppercase()})}}}
    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
     OutlinedButton({confirm=null},modifier=Modifier.weight(1f)) {Text("Cancel")}
     Button({confirm=null;vm.markPaid(action.second,method)},enabled=enabled && invoice!=null && state.paymentReviewId==null,modifier=Modifier.weight(1f)) {Text("Record payment")}
    }
    Spacer(Modifier.height(24.dp))
   }
  }
 }
 confirm?.takeIf {it.first!="paid"}?.let { action -> AlertDialog(onDismissRequest = { confirm = null }, title = { Text(when(action.first) { "quote" -> "Send quote?"; "invoice" -> "Create invoice?"; "paid" -> "Confirm payment received"; else -> "Send invoice?" }) },
  text = { Column { if(action.first == "paid") {
   Text("Record this only after receiving the full invoice amount.")
   listOf("cash", "card", "bank_transfer").forEach { option -> Row { RadioButton(method == option, { method = option }); Text(au.mainspring.nativeapp.ui.statusLabel(option)) } }
  } else Text("${if(action.first == "invoice") "Create the invoice using this quote's totals." else "Send this document using the customer's saved contact details."}") } },
  confirmButton = { Button(onClick = { confirm = null; when(action.first) { "quote" -> vm.sendQuote(action.second); "invoice" -> vm.createInvoice(action.second); "paid" -> vm.markPaid(action.second, method); else -> vm.sendInvoice(action.second) } }) { Text("Confirm") } },
  dismissButton = { TextButton(onClick = { confirm = null }) { Text("Cancel") } }) }
}

