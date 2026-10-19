package au.mainspring.nativeapp

import java.time.LocalDate
import java.time.format.DateTimeParseException

/** Query arguments shared by category-summary, gst-summary and the sales export. */
data class RangeQuery(val period: String?, val referenceDate: String?, val dateFrom: String?, val dateTo: String?)

/** A report window: a calendar period (day/week/month/quarter) or a custom inclusive date range. */
data class ReportRange(val period: String = "month", val dateFrom: String? = null, val dateTo: String? = null) {
    val custom: Boolean get() = period == CUSTOM

    /** Null when the range can be requested; otherwise a message to show next to the picker. */
    fun validate(): String? {
        if(!custom) return if(period in PERIODS) null else "Choose day, week, month, quarter or a custom range."
        val from = parse(dateFrom) ?: return "Choose a start date."
        val to = parse(dateTo) ?: return "Choose an end date."
        return if(to.isBefore(from)) "The end date must be on or after the start date." else null
    }

    fun query(today: String): RangeQuery =
        if(custom) RangeQuery(null, null, dateFrom, dateTo) else RangeQuery(period, today, null, null)

    fun fileLabel(): String = if(custom) "${dateFrom}_${dateTo}" else period

    fun describe(): String = if(custom) "$dateFrom to $dateTo" else period

    companion object {
        const val CUSTOM = "custom"
        val PERIODS = listOf("day", "week", "month", "quarter")
        private fun parse(value: String?): LocalDate? = try { value?.let(LocalDate::parse) } catch(_: DateTimeParseException) { null }
    }
}

/** Chart helpers, kept pure so they can be unit tested. */
object ReportCharts {
    /** Each value as a 0..1 fraction of the largest; all zero when nothing is positive. */
    fun fractions(values: List<Long>): List<Float> {
        val max = values.maxOrNull()?.takeIf { it > 0 } ?: return values.map { 0f }
        return values.map { (it.coerceAtLeast(0).toFloat() / max.toFloat()) }
    }

    /** "2026-10" becomes "Oct"; anything unparseable is returned unchanged. */
    fun monthLabel(month: String): String {
        val number = month.substringAfter('-', "").toIntOrNull() ?: return month
        val names = listOf("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        return names.getOrNull(number - 1) ?: month
    }

    /** "$1.2k", "$850" or "$2.5m" for narrow chart labels. */
    fun compactMoney(cents: Long): String {
        val dollars = cents / 100.0
        return when {
            dollars >= 1_000_000 -> "$" + String.format(java.util.Locale.UK, "%.1fm", dollars / 1_000_000)
            dollars >= 1_000 -> "$" + String.format(java.util.Locale.UK, "%.1fk", dollars / 1_000)
            else -> "$" + dollars.toLong()
        }
    }

    fun minutesLabel(minutes: Int): String {
        val m = minutes.coerceAtLeast(0)
        return if(m < 60) "${m}m" else "${m / 60}h ${m % 60}m"
    }
}
