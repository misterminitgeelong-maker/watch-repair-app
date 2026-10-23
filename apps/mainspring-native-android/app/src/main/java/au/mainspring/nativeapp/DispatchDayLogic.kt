package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AutoKeyJobRead
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** A picked day equal to today means "use the live Today list"; anything else is a specific scheduled day. */
fun resolveDispatchDay(picked: LocalDate, today: LocalDate): LocalDate? = picked.takeIf { it != today }

/** Header text for the day being viewed, e.g. "Today", "Tomorrow" or "Fri 23 Oct". */
fun dispatchDayLabel(day: LocalDate?, today: LocalDate): String = when {
    day == null || day == today -> "Today"
    day == today.plusDays(1) -> "Tomorrow"
    day == today.minusDays(1) -> "Yesterday"
    else -> day.format(DateTimeFormatter.ofPattern("EEE d MMM", Locale.forLanguageTag("en-AU")))
}

/** Web dispatch "Unscheduled" list: no booking time, still open, respecting the technician lane. */
fun dispatchUnscheduled(jobs: List<AutoKeyJobRead>, lane: String): List<AutoKeyJobRead> =
    jobs.filter { it.scheduledAt == null && it.status !in SLA_CLOSED &&
        (lane == "all" || (lane == "none" && it.assignedUserId == null) || it.assignedUserId == lane) }

/** Jobs that POS can attach a sale to: open jobs for the chosen customer (web `active_only` list). */
fun posLinkableJobs(jobs: List<AutoKeyJobRead>, customerId: String): List<AutoKeyJobRead> =
    if(customerId.isBlank()) emptyList() else jobs.filter { it.customerId == customerId && it.status !in SLA_CLOSED }
