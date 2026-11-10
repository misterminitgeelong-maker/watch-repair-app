package au.mainspring.nativeapp

import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class RouteMapContentTest {
    @Test fun onlyLocalRendererAssetsAndBoundedHttpsOsmTilesAreAllowed() {
        assertEquals("route-map/index.html", routeMapLocalAsset("$ROUTE_MAP_ORIGIN/"))
        assertEquals("route-map/leaflet.js", routeMapLocalAsset("$ROUTE_MAP_ORIGIN/leaflet.js"))
        assertNull(routeMapLocalAsset("https://mainspring-map.invalid.evil/leaflet.js"))
        assertNull(routeMapLocalAsset("$ROUTE_MAP_ORIGIN/../secrets"))
        assertTrue(isRouteMapTileUrl("https://tile.openstreetmap.org/12/3702/2501.png"))
        listOf("http://tile.openstreetmap.org/12/1/1.png", "https://tile.openstreetmap.org.evil/12/1/1.png", "https://tile.openstreetmap.org/99/1/1.png", "https://tile.openstreetmap.org/1/12/1.png", "https://tile.openstreetmap.org/12/1/1.png?address=private", "https://user@tile.openstreetmap.org/12/1/1.png").forEach { assertFalse(it, isRouteMapTileUrl(it)) }
    }
    @Test fun customerTextRemainsJsonDataAndInvalidCoordinatesNeverCreatePins() {
        val name = "</script><img src=x onerror=alert(1)> & Customer"
        val json = routeMapPayload(listOf(RouteMapPin("job", name, "1 Test Street", "Booked", 1, -37.8, 145.0), RouteMapPin("bad", "Invalid", "", "", 2, Double.NaN, 145.0)))
        assertFalse(json.contains("<")); assertFalse(json.contains("</script>"))
        val pins = JsonParser.parseString(json).asJsonArray
        assertEquals(1, pins.size()); assertEquals(name, pins[0].asJsonObject["label"].asString)
        assertEquals(-37.8, pins[0].asJsonObject["lat"].asDouble, 0.0)
    }
    @Test fun deviceGeocoderStateNamesMapToRoutingCodes() {
        assertEquals("VIC", australianStateCode("Victoria")); assertEquals("NSW", australianStateCode(" nsw "))
        assertEquals("ACT", australianStateCode("Australian Capital Territory")); assertNull(australianStateCode("Unknown"))
    }
}
