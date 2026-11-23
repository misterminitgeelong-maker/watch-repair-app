package au.mainspring.nativeapp.ui

import java.util.Locale

fun formatCents(cents: Int, currency: String): String {
    val major = cents / 100.0
    return String.format(Locale.US, "%.2f %s", major, currency)
}

/** Cents as a plain "12.50" string for prefilling amount fields. */
fun plainDollars(cents: Int): String = java.math.BigDecimal(cents).movePointLeft(2).setScale(2).toPlainString()

private val DOLLAR_CURRENCIES = setOf("AUD", "USD", "NZD", "CAD", "SGD", "HKD")

/**
 * Display format matching the web and backend (`$1,234.50`, `-$120.00`): symbol prefix, thousands separators and the
 * sign outside the symbol. Non-dollar currencies are prefixed with their code. A blank currency is treated as AUD.
 * [formatCents] keeps its older "12.50 AUD" shape for existing call sites.
 */
fun formatMoney(cents: Long, currency: String?): String {
    val code = currency?.trim()?.uppercase().orEmpty().ifEmpty { "AUD" }
    val symbol = if(code in DOLLAR_CURRENCIES) "$" else "$code "
    val sign = if(cents < 0) "-" else ""
    return sign + symbol + String.format(Locale.US, "%,.2f", java.math.BigDecimal.valueOf(cents, 2).abs())
}

fun formatMoney(cents: Int, currency: String?): String = formatMoney(cents.toLong(), currency)

/** Quantity x unit price in whole cents, rounded half-up like the backend's `gst.line_total_cents` (quantity may be fractional). */
fun lineTotalCents(unitPriceCents: Int, quantity: Double): Int =
    java.math.BigDecimal.valueOf(quantity).multiply(java.math.BigDecimal(unitPriceCents)).setScale(0, java.math.RoundingMode.HALF_UP).toInt()
