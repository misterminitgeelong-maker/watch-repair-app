package au.mainspring.nativeapp.ui

import java.util.Locale

fun formatCents(cents: Int, currency: String): String {
    val major = cents / 100.0
    return String.format(Locale.US, "%.2f %s", major, currency)
}

/** Cents as a plain "12.50" string for prefilling amount fields. */
fun plainDollars(cents: Int): String = java.math.BigDecimal(cents).movePointLeft(2).setScale(2).toPlainString()
