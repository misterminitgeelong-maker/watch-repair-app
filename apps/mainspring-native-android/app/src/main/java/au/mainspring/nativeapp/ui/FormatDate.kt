package au.mainspring.nativeapp.ui

import java.time.*
import java.time.format.DateTimeFormatter
import java.util.Locale

fun formatShopDate(value: String, zone: String = au.mainspring.nativeapp.TokenStore.calendarTimezone()): String = try {
    if (value.length == 10) LocalDate.parse(value).format(DateTimeFormatter.ofPattern("dd/MM/yyyy", Locale.forLanguageTag("en-AU")))
    else {
        val instant = try { OffsetDateTime.parse(value).toInstant() } catch (_: Exception) { LocalDateTime.parse(value).toInstant(ZoneOffset.UTC) }
        instant.atZone(ZoneId.of(zone)).format(DateTimeFormatter.ofPattern("dd/MM/yyyy h:mm a", Locale.forLanguageTag("en-AU")))
    }
} catch (_: Exception) { value }

fun scheduleInputDate(value: String, zone: String): String {
    val instant = try { OffsetDateTime.parse(value).toInstant() } catch (_: Exception) { LocalDateTime.parse(value).toInstant(ZoneOffset.UTC) }
    return instant.atZone(ZoneId.of(zone)).format(DateTimeFormatter.ofPattern("dd/MM/uuuu HH:mm"))
}
