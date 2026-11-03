package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.RepairOption
import au.mainspring.nativeapp.ui.filterRepairs
import au.mainspring.nativeapp.ui.formatCents
import au.mainspring.nativeapp.ui.repairSummary
import org.junit.Assert.assertEquals
import org.junit.Test

class RepairMultiSelectLogicTest {
    private val options = listOf(
        RepairOption("battery", "Battery replacement", 4500, "$45.00", "Quartz"),
        RepairOption("band", "Band resize", 2000, "$20.00", "Straps"),
        RepairOption("overhaul", "Full overhaul", null, "Quote required", "Mechanical"),
    )

    @Test fun summaryWhenEmptyIsPlaceholder() = assertEquals("Select repairs (optional)", repairSummary(0, null))
    @Test fun summarySingular() = assertEquals("1 repair · ${formatCents(4500, "AUD")}", repairSummary(1, 4500))
    @Test fun summaryPlural() = assertEquals("3 repairs · ${formatCents(12000, "AUD")}", repairSummary(3, 12000))
    @Test fun summaryWithQuote() = assertEquals("2 repairs · ${formatCents(4500, "AUD")} + quote", repairSummary(2, 4500, hasQuote = true))
    @Test fun summaryOnlyQuote() = assertEquals("1 repair · quote required", repairSummary(1, 0, hasQuote = true))

    @Test fun filterByNameAndGroupIgnoresCase() {
        assertEquals(listOf("band"), filterRepairs(options, "RESIZE").map { it.key })
        assertEquals(listOf("battery"), filterRepairs(options, "quartz").map { it.key })
        assertEquals(3, filterRepairs(options, "  ").size)
        assertEquals(0, filterRepairs(options, "zzz").size)
    }
}
