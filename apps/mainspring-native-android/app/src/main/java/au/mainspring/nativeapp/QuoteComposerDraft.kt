package au.mainspring.nativeapp
import au.mainspring.nativeapp.api.MobileQuoteLine
import java.math.BigDecimal
import java.math.RoundingMode

/** Keep server totals representable in the native cents models, including NZ's 15% GST. */
fun validateQuoteAmountRange(lines: List<MobileQuoteLine>) {
 require(lines.isNotEmpty() && lines.size <= 30) { "Add between one and thirty quote lines." }
 val subtotal = lines.fold(BigDecimal.ZERO) { total,line ->
  require(line.quantity.isFinite() && line.quantity > 0 && line.quantity <= 10000 && line.unitCents in 0..100_000_000) { "Check each line's quantity and unit price." }
  total + BigDecimal.valueOf(line.quantity).multiply(BigDecimal.valueOf(line.unitCents.toLong())).setScale(0, RoundingMode.HALF_UP)
 }
 require(subtotal.multiply(BigDecimal("1.15")).setScale(0,RoundingMode.HALF_UP) <= BigDecimal.valueOf(Int.MAX_VALUE.toLong())) { "This quote exceeds the amount supported by the native app. Reduce the quantity or split the work into separate quotes." }
}

data class QuoteLineDraft(val description: String = "", val quantity: String = "1", val price: String = "", val discountType: String = "none", val discount: String = "",
    /** Two-outcome quotes: "A" or "B" when the line belongs to one outcome, null when it applies to both. */ val option: String? = null)
data class QuoteComposerDraft(val lines: List<QuoteLineDraft> = listOf(QuoteLineDraft()), val gst: Boolean = true, val inclusive: Boolean = true, val gstChoiceMade: Boolean = false, val lastResetVersion: String? = null,
    val twoOutcome: Boolean = false, val labelA: String? = null, val labelB: String? = null)

data class QuotePreview(val subtotal: Long,val tax: Long,val total: Long)
fun quotePreview(draft: QuoteComposerDraft,currency: String): QuotePreview {
 val lines=quoteLinesFromDraft(draft.lines)
 val sum=lines.fold(BigDecimal.ZERO) {total,line ->total+BigDecimal.valueOf(line.quantity).multiply(BigDecimal.valueOf(line.unitCents.toLong())).setScale(0,RoundingMode.HALF_UP)}
 val rate=when(currency) {"AUD"->BigDecimal("0.10");"NZD"->BigDecimal("0.15");else->throw IllegalArgumentException("The shop's GST rate is unavailable.")}
 val tax=if(!draft.gst) BigDecimal.ZERO else if(draft.inclusive) sum.multiply(rate).divide(BigDecimal.ONE+rate,0,RoundingMode.HALF_UP) else sum.multiply(rate).setScale(0,RoundingMode.HALF_UP)
 return if(draft.gst && draft.inclusive) QuotePreview((sum-tax).longValueExact(),tax.longValueExact(),sum.longValueExact()) else QuotePreview(sum.longValueExact(),tax.longValueExact(),(sum+tax).longValueExact())
}
/** Per-unit discounts precede GST; exact integer rounding matches the current web POS. */
fun discountedUnitCents(unitCents: Int, type: String, value: String): Int {
 require(unitCents >= 0) { "Unit price cannot be negative." }
 require(type in listOf("none", "percent", "amount")) { "Choose a valid discount type." }
 if(type == "none" || value.isBlank()) return unitCents
 val hundredths = dollarsToCentsChecked(value)
 if(type == "percent") require(hundredths <= 10000) { "Percentage discount cannot exceed 100%." }
 val discount = if(type == "amount") hundredths else ((unitCents.toLong() * hundredths + 5000) / 10000).toInt()
 require(discount <= unitCents) { "Dollar discount cannot exceed the item price." }
 return unitCents - discount
}
fun quoteLinesFromDraft(draft: List<QuoteLineDraft>): List<MobileQuoteLine> {
 require(draft.isNotEmpty() && draft.size <= 30) { "Add between one and thirty quote lines." }
 return draft.mapIndexed { index, line ->
  require(line.description.isNotBlank()) { "Enter a description for line ${index+1}." }
  require(line.price.isNotBlank()) { "Enter a unit price for line ${index+1}." }
  val quantity = line.quantity.toDoubleOrNull()
  require(quantity != null && quantity.isFinite() && quantity > 0 && quantity <= 10000) { "Enter a valid quantity for line ${index+1}." }
  val price = dollarsToCentsChecked(line.price); val discounted = discountedUnitCents(price, line.discountType, line.discount)
  val description = if(discounted == price) line.description.trim() else {
   val discountLabel = if(line.discountType == "percent") "${BigDecimal(line.discount).stripTrailingZeros().toPlainString()}% discount" else "$${BigDecimal(price - discounted).movePointLeft(2).setScale(2)} discount per item"
   "${line.description.trim()} ($discountLabel; was $${BigDecimal(price).movePointLeft(2).setScale(2)} each)"
  }
  MobileQuoteLine(description, quantity, discounted)
 }.also(::validateQuoteAmountRange)
}

/** A two-outcome quote split the way the web POS sends it: shared lines plus exactly two named options. */
data class QuoteOutcomeSplit(val shared: List<MobileQuoteLine>, val options: List<au.mainspring.nativeapp.api.MobileQuoteOptionCreate>)
fun quoteOutcomeSplit(draft: QuoteComposerDraft): QuoteOutcomeSplit {
 val labelA = draft.labelA.orEmpty().trim(); val labelB = draft.labelB.orEmpty().trim()
 require(labelA.isNotBlank() && labelB.isNotBlank()) { "Give both options a name, e.g. CAS3 and CAS3++." }
 require(labelA.length <= 120 && labelB.length <= 120) { "Option names can be up to 120 characters." }
 require(draft.lines.any { it.option == "A" } && draft.lines.any { it.option == "B" }) { "Each option needs at least one item of its own." }
 require(draft.lines.size <= 30) { "A quote can contain up to 30 lines." }
 fun convert(key: String?) = draft.lines.filter { it.option == key }.let { rows -> if(rows.isEmpty()) emptyList() else quoteLinesFromDraft(rows) }
 val split = QuoteOutcomeSplit(convert(null), listOf(
  au.mainspring.nativeapp.api.MobileQuoteOptionCreate(labelA, convert("A")), au.mainspring.nativeapp.api.MobileQuoteOptionCreate(labelB, convert("B"))))
 split.options.forEach { validateQuoteAmountRange(split.shared + it.lines) }
 return split
}
/** Per-option totals for the live preview: each option is the shared lines plus that option's own lines. */
fun quoteOutcomePreviews(draft: QuoteComposerDraft, currency: String): Map<String, QuotePreview> =
 listOf("A", "B").associateWith { key -> quotePreview(draft.copy(lines = draft.lines.filter { it.option == null || it.option == key }), currency) }
