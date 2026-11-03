package au.mainspring.nativeapp

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CustomServiceLogicTest {
    @Test fun priceParsesToCents() {
        assertEquals(1250, parseCustomServicePrice("12.50"))
        assertEquals(0, parseCustomServicePrice("0"))
        assertEquals(100000, parseCustomServicePrice("$1,000"))
        assertEquals(1, parseCustomServicePrice("0.005"))
    }

    @Test fun invalidPricesAreRejected() {
        assertNull(parseCustomServicePrice(""))
        assertNull(parseCustomServicePrice("abc"))
        assertNull(parseCustomServicePrice("-1"))
    }
}
