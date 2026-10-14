package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.MobileQuoteLine
import com.google.gson.Gson
import java.math.RoundingMode
import kotlinx.coroutines.CancellationException
import au.mainspring.nativeapp.ui.FlatPanel
import au.mainspring.nativeapp.ui.SectionLabel
import au.mainspring.nativeapp.ui.formatCents

@Composable fun QuoteComposer(draftKey: String, businessAccount: Boolean, enabled: Boolean, catalogue: Boolean,
 resetVersion: String? = null, quickSale: Boolean = false, currency: String? = TokenStore.shopValue("currency"), buttonLabel: String = "Save draft quote", modifier: Modifier = Modifier, sheetLayout: Boolean = false, secondaryLabel: String? = null, onSecondary: ((List<MobileQuoteLine>, Boolean, Boolean) -> Unit)? = null, onSave: (List<MobileQuoteLine>, Boolean, Boolean) -> Unit) {
 val drafts = remember(draftKey) { TokenStore.bindDrafts() }
 val gson = remember { Gson() }
 val initial = remember(draftKey) { try { gson.fromJson(drafts.loadMessageDraft(draftKey), QuoteComposerDraft::class.java) ?: QuoteComposerDraft(inclusive = !businessAccount) } catch(_: Exception) { QuoteComposerDraft(inclusive = !businessAccount) } }
 val saver = remember { Saver<QuoteComposerDraft, String>(save = { gson.toJson(it) }, restore = { gson.fromJson(it, QuoteComposerDraft::class.java) }) }
 var draft by rememberSaveable(draftKey, stateSaver = saver) { mutableStateOf(initial) }
 var expanded by rememberSaveable { mutableStateOf(0) }
 var categories by remember { mutableStateOf<List<String>>(emptyList()) }
 var itemQuery by rememberSaveable { mutableStateOf("") }
 var showBundles by rememberSaveable {mutableStateOf(!sheetLayout)}
 var pricingOptions by rememberSaveable {mutableStateOf(!sheetLayout)}
 var error by remember { mutableStateOf<String?>(null) }; var picking by remember { mutableStateOf(false) }
 fun persist(value: QuoteComposerDraft) { draft = value; error = null; drafts.saveMessageDraft(draftKey, gson.toJson(value)) }
 fun change(index: Int, value: QuoteLineDraft) { persist(draft.copy(lines = draft.lines.toMutableList().also { it[index] = value })) }
 LaunchedEffect(resetVersion) { if(resetVersion != null && draft.lastResetVersion != resetVersion) { draft = QuoteComposerDraft(inclusive = !businessAccount,lastResetVersion=resetVersion); expanded=0; drafts.saveMessageDraft(draftKey,gson.toJson(draft)); error = null } }
 LaunchedEffect(businessAccount) { if(!draft.gstChoiceMade && draft.inclusive == businessAccount) persist(draft.copy(inclusive = !businessAccount)) }
 LaunchedEffect(draftKey) { if(catalogue) try {categories = au.mainspring.nativeapp.api.ApiClient.api.pricingMeta().categories} catch(e: CancellationException) {throw e} catch(_: Exception) {categories=emptyList()} }
 fun addLines(newLines: List<QuoteLineDraft>) {
  val existing = if(draft.lines.size == 1 && draft.lines[0].description.isBlank() && draft.lines[0].price.isBlank()) emptyList() else draft.lines
  if(quickSale && newLines.size==1) {
   val line=newLines.single()
   val index=existing.indexOfFirst {it.description==line.description && it.price==line.price && it.discountType=="none"}
   if(index>=0) {
    val quantity=existing[index].quantity.toBigDecimalOrNull()
    if(quantity==null || quantity+java.math.BigDecimal.ONE>java.math.BigDecimal("10000")) {error="Check this item's quantity before adding more.";return}
    persist(draft.copy(lines=existing.toMutableList().also {it[index]=it[index].copy(quantity=(quantity+java.math.BigDecimal.ONE).stripTrailingZeros().toPlainString())}));expanded=-1;return
   }
  }
  if(existing.size + newLines.size > 30) {error="A quote can contain up to 30 lines.";return}
  persist(draft.copy(lines=existing+newLines)); expanded=-1
 }
 @Composable fun totalsAndSave() {
  val preview=try {currency?.let {quotePreview(draft,it)}} catch(_: Exception) {null}
  if(sheetLayout && preview==null) Text("Enter an item and price to see the total.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
  val validLines=try {validateQuoteAmountRange(quoteLinesFromDraft(draft.lines));true} catch(_: Exception) {false}
  if(au.mainspring.nativeapp.ui.LocalCalibre.current) preview?.let {total->Column(Modifier.fillMaxWidth()) {
   HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
   Column(Modifier.padding(vertical=14.dp),verticalArrangement=Arrangement.spacedBy(4.dp)) {
    au.mainspring.nativeapp.ui.MonoLabel("Cart total")
    Text(formatCents(total.total.toInt(),currency!!),style=MaterialTheme.typography.headlineLarge.copy(fontWeight=androidx.compose.ui.text.font.FontWeight.Normal))
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {au.mainspring.nativeapp.ui.MonoLabel(if(draft.inclusive) "Included GST" else "GST");au.mainspring.nativeapp.ui.MonoLabel(formatCents(total.tax.toInt(),currency!!))}
   }
   HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
  } } else preview?.let {total->au.mainspring.nativeapp.ui.HeroCard {
   Text("CART TOTAL",style=MaterialTheme.typography.labelSmall)
   Text(formatCents(total.total.toInt(),currency!!),style=MaterialTheme.typography.headlineLarge)
   Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {Text(if(draft.inclusive) "Included GST" else "GST",style=MaterialTheme.typography.bodySmall);Text(formatCents(total.tax.toInt(),currency!!),style=MaterialTheme.typography.bodySmall)}
  } }

  Button(onClick = { try { onSave(quoteLinesFromDraft(draft.lines), draft.gst, draft.inclusive) } catch(e: Exception) { error = e.userMessage() } }, enabled = enabled && validLines,modifier=Modifier.fillMaxWidth().heightIn(min=52.dp)) { Text(buttonLabel) }
  if(secondaryLabel != null && onSecondary != null) OutlinedButton(onClick = { try { onSecondary(quoteLinesFromDraft(draft.lines), draft.gst, draft.inclusive) } catch(e: Exception) { error = e.userMessage() } }, enabled = enabled && validLines, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Text(secondaryLabel) }
 }
 Column(modifier) {
 Column(if(sheetLayout) Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal=16.dp) else Modifier,verticalArrangement = Arrangement.spacedBy(10.dp)) {

  error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
  if(catalogue && currency == "AUD") {
   SectionLabel(if(quickSale) "Quick items" else "One-tap bundles")
   if(!sheetLayout || showBundles || quickSale) Text("Editable retail presets · AUD",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
   if(sheetLayout && !quickSale) TextButton({showBundles=!showBundles},enabled=enabled) {Text(if(showBundles) "Hide bundles" else "Choose a bundle") }
   if(quickSale) {
    au.mainspring.nativeapp.ui.AtelierTextField(itemQuery,{itemQuery=it},label={Text("Find a quick item")},singleLine=true,modifier=Modifier.fillMaxWidth())
    val rows=MOBILE_QUICK_ITEMS.filter {it.category in categories}.filter {row->itemQuery.lowercase().split(Regex("[^a-z0-9]+")).filter {it.isNotBlank()}.all {term->("${row.label} ${row.description}").lowercase().contains(term)}}
    rows.chunked(3).forEach { group -> Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)) {
     group.forEach {item->OutlinedButton({addLines(listOf(QuoteLineDraft("${item.label} - ${item.description}","1",java.math.BigDecimal.valueOf(item.cents.toLong(),2).toPlainString())))},enabled=enabled,modifier=Modifier.weight(1f),contentPadding=PaddingValues(8.dp)) {
      Column {Text(item.label,style=MaterialTheme.typography.labelSmall);Text(formatCents(item.cents,"AUD"),style=MaterialTheme.typography.labelSmall)}
     }}
     repeat(3-group.size) {Spacer(Modifier.weight(1f))}
    } }
   } else if(showBundles && ("vehicle_key" in categories || "general_service" in categories)) {
    MOBILE_QUOTE_BUNDLES.chunked(2).forEach {group->Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {group.forEach {bundle->OutlinedButton({addLines(bundle.lines)},enabled=enabled,modifier=Modifier.weight(1f),contentPadding=PaddingValues(10.dp)) {
     Column {Text(bundle.label,style=MaterialTheme.typography.labelLarge);Text(bundle.note,style=MaterialTheme.typography.bodySmall);Text(formatCents(bundle.lines.sumOf {dollarsToCentsChecked(it.price)},"AUD"),style=MaterialTheme.typography.labelLarge)}
    }} } }
   }
  }
  SectionLabel("Line items")
  draft.lines.forEachIndexed { index, line ->
   if(line.description.isNotBlank() || expanded!=index || !sheetLayout) FlatPanel {
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
     Text(line.description.ifBlank {"Line ${index+1}"},Modifier.weight(1f),style=MaterialTheme.typography.titleSmall)
     TextButton({expanded=if(expanded==index) -1 else index},enabled=enabled) {Text(if(expanded==index) "Done" else "Edit line ${index+1}")}
    }
    if(line.price.isNotBlank()) Text("${line.quantity} × ${line.price}",style=MaterialTheme.typography.bodySmall)
   }
   if(expanded==index) {
   au.mainspring.nativeapp.ui.AtelierTextField(line.description, { change(index, line.copy(description = it)) }, label = { Text("Description") }, enabled = enabled, modifier = Modifier.fillMaxWidth())
   Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
    au.mainspring.nativeapp.ui.AtelierTextField(line.quantity, { change(index, line.copy(quantity = it)) }, label = { Text("Quantity") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), enabled = enabled, modifier = Modifier.weight(1f), singleLine = true)
    au.mainspring.nativeapp.ui.AtelierTextField(line.price, { change(index, line.copy(price = it)) }, label = { Text("Unit price ($)") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), enabled = enabled, modifier = Modifier.weight(1f), singleLine = true)
   }
   if((pricingOptions || line.discountType!="none") && au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.MonoLabel("Discount")
   if(pricingOptions || line.discountType!="none") Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
    listOf("none" to "No discount", "percent" to "% discount", "amount" to "$ discount").forEach { (key,label) -> au.mainspring.nativeapp.ui.AtelierChip(line.discountType == key, { change(index, line.copy(discountType = key)) }, enabled = enabled, label = { Text(label) }) }
   }
   if(line.discountType != "none") au.mainspring.nativeapp.ui.AtelierTextField(line.discount, { change(index, line.copy(discount = it)) }, label = { Text(if(line.discountType == "percent") "Discount percentage" else "Discount per item ($)") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), enabled = enabled, modifier = Modifier.fillMaxWidth(), singleLine = true)
   }
   if(draft.lines.size > 1) TextButton(onClick = { persist(draft.copy(lines = draft.lines.filterIndexed { i,_ -> i != index })) }, enabled = enabled) { Text("Remove line ${index+1}") }
  }
  if(draft.lines.size < 30) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
   OutlinedButton(onClick = { persist(draft.copy(lines = draft.lines + QuoteLineDraft())); expanded=draft.lines.lastIndex }, enabled = enabled) { Text("Add line") }
   if(catalogue) OutlinedButton(onClick = { picking = true }, enabled = enabled) { Text("Catalogue item") }
  }
  if(sheetLayout) TextButton({pricingOptions=!pricingOptions},enabled=enabled) {Text(if(pricingOptions) "Hide pricing options" else "Discount & GST options")}
  if(pricingOptions) {
  Row { Checkbox(draft.gst, { persist(draft.copy(gst = it)) }, enabled = enabled); Text("GST applies") }
  if(draft.gst) Row { Checkbox(draft.inclusive, { persist(draft.copy(inclusive = it, gstChoiceMade = true)) }, enabled = enabled); Text("Entered prices include GST") }
  }
  if(!sheetLayout) totalsAndSave()
  }
  if(sheetLayout) Surface(color=MaterialTheme.colorScheme.surface,shadowElevation=4.dp) {
   Column(Modifier.fillMaxWidth().padding(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {totalsAndSave()}
  }
 }

 if(picking) PricingPicker(onClose = { picking = false }, onSelect = { row ->
  val price = row.price?.setScale(2, RoundingMode.HALF_UP)?.toPlainString().orEmpty()
  val line = QuoteLineDraft(row.label(), "1", price)
  val lines = if(draft.lines.size == 1 && draft.lines[0].description.isBlank() && draft.lines[0].price.isBlank()) listOf(line) else draft.lines + line
  persist(draft.copy(lines = lines)); picking = false
 })
}
