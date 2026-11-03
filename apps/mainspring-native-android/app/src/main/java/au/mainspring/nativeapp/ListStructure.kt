package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.TenantEventLogRead
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset

/** Pure grouping / sorting helpers behind the structured list screens (Jobs, Customers, Inbox). */

val JOB_SORTS = listOf("default" to "Default", "newest" to "Newest", "oldest" to "Oldest", "due" to "Due date", "customer" to "Customer")

fun sortHubJobs(jobs: List<HubJob>, sort: String): List<HubJob> = when(sort) {
    "newest" -> jobs.sortedWith(compareByDescending<HubJob> { it.createdAt }.thenBy { it.sortKey })
    "oldest" -> jobs.sortedWith(compareBy<HubJob> { it.createdAt }.thenBy { it.sortKey })
    "due" -> jobs.sortedWith(compareBy<HubJob> { it.dueDate.isNullOrBlank() }.thenBy { it.dueDate.orEmpty().take(10) }.thenBy { it.sortKey })
    "customer" -> jobs.sortedWith(compareBy<HubJob> { it.customer.isNullOrBlank() }.thenBy { it.customer.orEmpty().lowercase() }.thenBy { it.sortKey })
    else -> jobs.sortedBy { it.sortKey }
}

fun countLabel(count: Int, singular: String, plural: String = singular + "s", more: Boolean = false) =
    "$count${if(more) "+" else ""} ${if(count == 1 && !more) singular else plural}"

/** Section letter for a customer name: first letter uppercased, "#" for digits/symbols/blank. */
fun alphaLetter(name: String): String {
    val c = name.trim().firstOrNull() ?: return "#"
    return if(c.isLetter()) c.uppercaseChar().toString() else "#"
}

/** Groups consecutive items sharing a letter, so already-sorted lists (asc or desc) keep their order. */
fun <T> alphaSections(items: List<T>, name: (T) -> String): List<Pair<String, List<T>>> {
    val out = mutableListOf<Pair<String, MutableList<T>>>()
    for(item in items) {
        val letter = alphaLetter(name(item))
        if(out.lastOrNull()?.first == letter) out.last().second.add(item) else out.add(letter to mutableListOf(item))
    }
    return out
}

val INBOX_FILTERS = listOf("all" to "All", "jobs" to "Jobs", "money" to "Money", "messages" to "Messages")

/** Maps an alert's type to a filter bucket: "money", "messages" or "jobs" (everything else). */
fun inboxCategory(ev: TenantEventLogRead): String {
    val t = ev.eventType.lowercase()
    return when {
        listOf("payment", "invoice", "refund", "card", "stripe", "paid", "deposit", "quote").any { t.contains(it) } || ev.entityType == "invoice" -> "money"
        listOf("sms", "message", "reply", "email", "chat").any { t.contains(it) } -> "messages"
        else -> "jobs"
    }
}

fun filterInbox(events: List<TenantEventLogRead>, filter: String) = if(filter == "all") events else events.filter { inboxCategory(it) == filter }

private fun parseInstant(value: String): Instant? = try { OffsetDateTime.parse(value).toInstant() } catch(_: Exception) {
    try { LocalDateTime.parse(value).toInstant(ZoneOffset.UTC) } catch(_: Exception) { null }
}

/** "Today", "Yesterday", "This week" (within the last 7 days) or "Earlier". */
fun dayBucket(createdAt: String, now: Instant, zone: ZoneId): String {
    val d = parseInstant(createdAt)?.atZone(zone)?.toLocalDate() ?: return "Earlier"
    val today: LocalDate = now.atZone(zone).toLocalDate()
    val age = java.time.temporal.ChronoUnit.DAYS.between(d, today)
    return when { age <= 0 -> "Today"; age == 1L -> "Yesterday"; age < 7 -> "This week"; else -> "Earlier" }
}

fun inboxDaySections(events: List<TenantEventLogRead>, now: Instant, zone: ZoneId): List<Pair<String, List<TenantEventLogRead>>> {
    val order = listOf("Today", "Yesterday", "This week", "Earlier")
    val grouped = events.groupBy { dayBucket(it.createdAt, now, zone) }
    return order.mapNotNull { k -> grouped[k]?.let { k to it } }
}
