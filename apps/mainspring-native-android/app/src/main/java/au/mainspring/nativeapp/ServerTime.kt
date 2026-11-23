package au.mainspring.nativeapp

import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset

/**
 * Parses the timestamp shapes the API returns: offset/Z ("2026-11-01T03:00:00Z", "...+00:00"), naive UTC
 * ("2026-11-01T03:00:00[.ffffff]") and plain dates ("2026-11-01", taken as the start of that UTC day).
 * Returns null for null, blank or unreadable input; never throws.
 */
fun parseServerInstant(value: String?): Instant? {
    val v = value?.trim().orEmpty()
    if (v.isEmpty()) return null
    return runCatching { OffsetDateTime.parse(v).toInstant() }.getOrNull()
        ?: runCatching { Instant.parse(v) }.getOrNull()
        ?: runCatching { LocalDateTime.parse(v).toInstant(ZoneOffset.UTC) }.getOrNull()
        ?: runCatching { LocalDate.parse(v).atStartOfDay().toInstant(ZoneOffset.UTC) }.getOrNull()
}

/** The shop's calendar zone (from the signed-in session), falling back to the device zone if it is unreadable. */
fun shopZone(): ZoneId = runCatching { ZoneId.of(TokenStore.calendarTimezone()) }.getOrElse { ZoneId.systemDefault() }

/** Today's date on the shop calendar (not the device calendar). */
fun shopToday(zone: ZoneId = shopZone()): LocalDate = LocalDate.now(zone)

/**
 * The shop calendar date a server timestamp falls on. A plain date ("2026-11-24") is already a shop date and is
 * returned as is; timestamps are converted from their instant into [zone]. Null when unreadable.
 */
fun serverShopDate(value: String?, zone: ZoneId = shopZone()): LocalDate? {
    val v = value?.trim().orEmpty()
    if (v.length == 10) runCatching { return LocalDate.parse(v) }
    return parseServerInstant(v)?.atZone(zone)?.toLocalDate()
}
