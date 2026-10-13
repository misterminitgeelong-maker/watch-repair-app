package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobCreate
import au.mainspring.nativeapp.api.WatchCreate
import com.google.gson.Gson
import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test
import java.io.ByteArrayInputStream

class IntakeContractTest {
    @Test fun photoAtLimitIsAcceptedWithoutTruncation() {
        val bytes = ByteArray(8193) { (it % 255).toByte() }
        assertArrayEquals(bytes, readPhotoBounded(ByteArrayInputStream(bytes), bytes.size))
    }
    @Test(expected = IllegalArgumentException::class)
    fun oversizedPhotoIsRejectedBeforeUpload() {
        readPhotoBounded(ByteArrayInputStream(ByteArray(8193)), 8192)
    }
    @Test fun intakePayloadUsesBackendFieldNamesAndSelectedStatus() {
        val body = JsonParser.parseString(Gson().toJson(RepairJobCreate(watchId = "watch-1",
            title = "Battery replacement", priority = "urgent", status = "go_ahead"))).asJsonObject
        assertEquals("watch-1", body["watch_id"].asString)
        assertEquals("go_ahead", body["status"].asString)
        assertEquals("urgent", body["priority"].asString)
        assertFalse(body.has("watchId"))
        val watch = JsonParser.parseString(Gson().toJson(WatchCreate("customer-1", "Seiko", null, "123", "Scratched case"))).asJsonObject
        assertEquals("customer-1", watch["customer_id"].asString)
        assertEquals("123", watch["serial_number"].asString)
        assertEquals("Scratched case", watch["condition_notes"].asString)
    }
}
