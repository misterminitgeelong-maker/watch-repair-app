package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.phoneChatDay
import au.mainspring.nativeapp.ui.phoneChatTime
import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.Locale

class PhoneChatTimestampTest {
    @Test fun utcAndOffsetlessApiTimestampsUseTheSameShortShopTime() {
        assertEquals("11:02 am", phoneChatTime("2026-10-08T00:02:00Z").lowercase(Locale.ROOT))
        assertEquals("11:02 am", phoneChatTime("2026-10-08T00:02:00").lowercase(Locale.ROOT))
        assertEquals("11:02 am", phoneChatTime("2026-10-08T10:02:00+10:00").lowercase(Locale.ROOT))
    }
    @Test fun dayDividerUsesTheShopsDayAcrossUtcMidnight() {
        assertEquals("Fri, 9 Oct", phoneChatDay("2026-10-08T15:02:00Z"))
        assertEquals("Fri, 9 Oct", phoneChatDay("2026-10-08T15:02:00"))
        assertEquals("", phoneChatTime(""))
    }
}
