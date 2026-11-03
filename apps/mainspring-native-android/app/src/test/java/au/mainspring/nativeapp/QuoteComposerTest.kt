package au.mainspring.nativeapp
import org.junit.*
class QuoteComposerTest {
 @Test fun discountRoundingAndDescriptionsMatchWebPos() {
  val line = quoteLinesFromDraft(listOf(QuoteLineDraft("Mobile key", "2", "100", "percent", "10"))).single()
  Assert.assertEquals(9000, line.unitCents); Assert.assertEquals(2.0, line.quantity, 0.0)
  Assert.assertEquals("Mobile key (10% discount; was $100.00 each)", line.description)
  Assert.assertEquals(26, discountedUnitCents(29, "percent", "10"))
 }
 @Test fun fixedDiscountNeverAllowsNegativeUnitPrice() {
  Assert.assertEquals(1129, discountedUnitCents(1229, "amount", "1.00"))
  try { discountedUnitCents(29, "amount", ".30"); Assert.fail("Over-discount accepted") } catch(_: IllegalArgumentException) {}
  try { discountedUnitCents(29, "percent", "100.01"); Assert.fail("Over-discount accepted") } catch(_: IllegalArgumentException) {}
 }
 @Test fun invalidSavedDraftCannotProduceBackendLines() {
  try { quoteLinesFromDraft(listOf(QuoteLineDraft("Service", "NaN", "1"))); Assert.fail("NaN accepted") } catch(_: IllegalArgumentException) {}
  Assert.assertEquals(50, dollarsToCentsChecked(".50")); Assert.assertEquals(1200, dollarsToCentsChecked("12."))
 }
 @Test fun aggregateAmountCannotOverflowNativeCentsModels() {
  try { quoteLinesFromDraft(listOf(QuoteLineDraft("Fleet service", "10000", "1000000"))); Assert.fail("Overflow accepted") } catch(_:IllegalArgumentException) {}
  val normal = quoteLinesFromDraft(listOf(QuoteLineDraft("Fleet service", "100", "1000")))
  Assert.assertEquals(100000,normal.single().unitCents)
 }
}
