package au.mainspring.nativeapp

import org.junit.Assert.*
import org.junit.Test

class ReportRangeTest {
    @Test fun calendarPeriodSendsPeriodAndReferenceDateOnly() {
        val q = ReportRange("quarter").query("2026-10-15")
        assertEquals(RangeQuery("quarter", "2026-10-15", null, null), q)
        assertNull(ReportRange("quarter").validate())
    }

    @Test fun customRangeSendsDatesOnly() {
        val range = ReportRange(ReportRange.CUSTOM, "2026-09-01", "2026-09-30")
        assertNull(range.validate())
        assertEquals(RangeQuery(null, null, "2026-09-01", "2026-09-30"), range.query("2026-10-15"))
        assertEquals("2026-09-01_2026-09-30", range.fileLabel())
    }

    @Test fun customRangeNeedsBothDatesInOrder() {
        assertNotNull(ReportRange(ReportRange.CUSTOM, null, null).validate())
        assertNotNull(ReportRange(ReportRange.CUSTOM, "2026-09-01", null).validate())
        assertNotNull(ReportRange(ReportRange.CUSTOM, "2026-09-30", "2026-09-01").validate())
        assertNotNull(ReportRange(ReportRange.CUSTOM, "not-a-date", "2026-09-01").validate())
        assertNull(ReportRange(ReportRange.CUSTOM, "2026-09-01", "2026-09-01").validate())
    }

    @Test fun unknownPeriodIsRejected() = assertNotNull(ReportRange("year").validate())

    @Test fun fractionsScaleToLargestAndHandleEmptyData() {
        assertEquals(listOf(0.5f, 1f, 0f), ReportCharts.fractions(listOf(50, 100, 0)))
        assertEquals(listOf(0f, 0f), ReportCharts.fractions(listOf(0, 0)))
        assertEquals(emptyList<Float>(), ReportCharts.fractions(emptyList()))
        assertEquals(0f, ReportCharts.fractions(listOf(-5, 10))[0], 0f)
    }

    @Test fun labelsAreCompact() {
        assertEquals("Oct", ReportCharts.monthLabel("2026-10"))
        assertEquals("bad", ReportCharts.monthLabel("bad"))
        assertEquals("45m", ReportCharts.minutesLabel(45))
        assertEquals("2h 5m", ReportCharts.minutesLabel(125))
        assertEquals("$850", ReportCharts.compactMoney(85_000))
        assertEquals("$1.2k", ReportCharts.compactMoney(123_400))
        assertEquals("$2.5m", ReportCharts.compactMoney(250_000_000))
    }
}
