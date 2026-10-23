package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ProspectLead
import java.net.URLEncoder

/** `tel:` target for a phone number, or null when it has no digits. Spaces and punctuation are dropped, a leading + is kept. */
fun prospectTelUri(phone: String?): String? {
    val raw = phone?.trim().orEmpty()
    val digits = raw.filter { it.isDigit() }
    if(digits.length < 3) return null
    return "tel:" + (if(raw.startsWith("+")) "+" else "") + digits
}

/** Google Maps search link for a business (same URL the web uses). */
fun prospectMapsUri(name: String, address: String?): String =
    "https://www.google.com/maps/search/?api=1&query=" + URLEncoder.encode("$name ${address.orEmpty()}".trim(), "UTF-8")

/** Normalised website URL: adds https:// when no scheme is present, and only ever allows http or https. */
fun prospectWebsiteUri(site: String?): String? {
    val t = site?.trim().orEmpty()
    if(t.isEmpty() || t.any { it.isWhitespace() }) return null
    val lower = t.lowercase()
    return when {
        lower.startsWith("http://") || lower.startsWith("https://") -> t
        "://" in t -> null
        else -> "https://$t"
    }
}

/** Leads with a scheduled visit, soonest first (the "Visits" view); ISO timestamps sort lexically. */
fun prospectVisits(leads: List<ProspectLead>): List<ProspectLead> =
    leads.filter { !it.visit.isNullOrBlank() }.sortedBy { it.visit }
