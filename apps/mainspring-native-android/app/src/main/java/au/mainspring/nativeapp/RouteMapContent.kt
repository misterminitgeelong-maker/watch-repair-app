package au.mainspring.nativeapp

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.net.URI

const val ROUTE_MAP_ORIGIN = "https://mainspring-map.invalid"
data class RouteMapPin(val id: String, val label: String, val address: String, val status: String, val order: Int, val lat: Double, val lng: Double)

/** Only real geocodes enter the map; customer text is JSON data, never executable markup. */
fun routeMapPayload(pins: List<RouteMapPin>): String = JsonArray().apply {
    pins.filter { it.lat.isFinite() && it.lng.isFinite() && it.lat in -85.05112878..85.05112878 && it.lng in -180.0..180.0 }.take(100).forEach { p ->
        add(JsonObject().apply { addProperty("id", p.id); addProperty("label", p.label); addProperty("address", p.address); addProperty("status", p.status); addProperty("order", p.order); addProperty("lat", p.lat); addProperty("lng", p.lng) })
    }
}.toString().replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

/** The fallback needs only standard raster tiles from the same provider already used by the web app. */
fun isRouteMapTileUrl(raw: String): Boolean = runCatching {
    val uri = URI(raw)
    if(uri.scheme != "https" || uri.host != "tile.openstreetmap.org" || uri.port !in listOf(-1, 443) || uri.userInfo != null || uri.rawQuery != null || uri.rawFragment != null) return false
    val match = Regex("^/(\\d{1,2})/(\\d{1,6})/(\\d{1,6})\\.png$").matchEntire(uri.path) ?: return false
    val zoom = match.groupValues[1].toInt(); if(zoom !in 0..19) return false
    val max = 1 shl zoom
    match.groupValues[2].toInt() in 0 until max && match.groupValues[3].toInt() in 0 until max
}.getOrDefault(false)

fun routeMapLocalAsset(raw: String): String? = runCatching {
    val uri = URI(raw)
    if(uri.scheme != "https" || uri.host != "mainspring-map.invalid" || uri.port != -1 || uri.userInfo != null || uri.rawQuery != null || uri.rawFragment != null) return null
    when(uri.path) { "/" -> "route-map/index.html"; "/leaflet.js" -> "route-map/leaflet.js"; "/leaflet.css" -> "route-map/leaflet.css"; "/route-map.js" -> "route-map/route-map.js"; else -> null }
}.getOrNull()
