package au.mainspring.nativeapp

import com.google.gson.JsonParser
import org.junit.Assert.*
import org.junit.Test

class CustomFieldsTest {
    @Test fun parsesObjectKeepingOrderAndStringifyingValues() {
        val m = CustomFields.parse("""{"b":"2","a":3,"c":null,"d":true}""")
        assertEquals(listOf("b", "a", "c", "d"), m.keys.toList())
        assertEquals(listOf("2", "3", "", "true"), m.values.toList())
    }
    @Test fun blankInvalidOrNonObjectIsEmpty() {
        assertTrue(CustomFields.parse(null).isEmpty()); assertTrue(CustomFields.parse("  ").isEmpty())
        assertTrue(CustomFields.parse("{oops").isEmpty()); assertTrue(CustomFields.parse("[1,2]").isEmpty())
    }
    @Test fun readsFromJobDocument() {
        val job = JsonParser.parseString("""{"id":"1","custom_fields_json":"{\"Serial\":\"X1\"}"}""").asJsonObject
        assertEquals(mapOf("Serial" to "X1"), CustomFields.fromJob(job))
        assertTrue(CustomFields.fromJob(JsonParser.parseString("""{"custom_fields_json":null}""").asJsonObject).isEmpty())
        assertTrue(CustomFields.fromJob(JsonParser.parseString("{}").asJsonObject).isEmpty())
    }
    @Test fun cleanNameTrims() { assertEquals("Serial", CustomFields.cleanName("  Serial ")); assertNull(CustomFields.cleanName("   ")) }
}
