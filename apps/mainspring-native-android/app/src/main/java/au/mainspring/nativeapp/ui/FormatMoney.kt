package au.mainspring.nativeapp.ui

import java.util.Locale

fun formatCents(cents: Int, currency: String): String {
    val major = cents / 100.0
    return String.format(Locale.US, "%.2f %s", major, currency)
}
