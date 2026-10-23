package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.WatchCatalogueItem
import au.mainspring.nativeapp.api.WatchRepairsCombo
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlin.math.floor

fun dollarsToCentsChecked(text: String): Int {
    if (text.isBlank()) return 0
    require(Regex("(?:\\d+(?:\\.\\d{0,2})?|\\.\\d{1,2})").matches(text.trim())) { "Enter a non-negative dollar amount with up to two decimal places." }
    val cents = BigDecimal(text.trim()).movePointRight(2).setScale(0, RoundingMode.UNNECESSARY).intValueExact()
    require(cents in 0..100_000_000) { "Amount must be between $0 and $1,000,000." }
    return cents
}

fun collectionDateIso(text: String): String? {
    if (text.isBlank()) return null
    return LocalDate.parse(text.trim(), DateTimeFormatter.ofPattern("dd/MM/uuuu")
        .withResolverStyle(java.time.format.ResolverStyle.STRICT)).toString()
}

/** Matches NewJobModal.calculateRepairsTotal, including first-match combo precedence. */
fun repairsTotal(items: List<WatchCatalogueItem>, combos: List<WatchRepairsCombo>): Int {
    val keys = items.map { it.key }.toSet()
    val applied = mutableSetOf<String>()
    var total = 0
    combos.firstOrNull { !it.keys.isNullOrEmpty() && it.totalCents != null && it.keys.all(keys::contains) }?.let {
        total += it.totalCents!!; applied.addAll(it.keys!!)
    }
    val battery = combos.firstOrNull { it.batteryKey != null && it.bandKeys != null }
    items.filterNot { it.key in applied }.forEach { item ->
        val price = item.priceCents ?: 0
        total += if (battery?.batteryKey in keys && item.key in (battery?.bandKeys ?: emptyList()) && (battery?.bandDiscountPercent ?: 0.0) > 0)
            floor(price * (1 - battery!!.bandDiscountPercent!! / 100) + 0.5).toInt() else price
    }
    return total
}
