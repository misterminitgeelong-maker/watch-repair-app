package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobRead
import java.time.LocalDate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class QueueDayLogicTest {
    private val today = LocalDate.of(2026, 10, 20)
    private fun row(id: String, due: String? = null, priority: String = "normal", created: String? = "2026-10-01T00:00:00Z", status: String = "go_ahead") =
        QueueRow(id, status, priority, due, created)

    @Test fun urgencyBuckets() {
        assertEquals(0, collectionUrgency("2026-10-19", today))
        assertEquals(1, collectionUrgency("2026-10-20", today))
        assertEquals(1, collectionUrgency("2026-10-20T09:00:00Z", today))
        assertEquals(2, collectionUrgency("2026-10-21", today))
        assertEquals(3, collectionUrgency("2026-10-22", today))
        assertEquals(3, collectionUrgency(null, today))
        assertEquals(3, collectionUrgency("not a date", today))
    }

    @Test fun sortIsUrgencyThenPriorityThenAge() {
        val ids = sortQueueRows(listOf(
            row("late-normal"), row("late-urgent", priority = "urgent"), row("today", due = "2026-10-20"),
            row("overdue", due = "2026-10-10"), row("old", created = "2026-09-01T00:00:00Z"),
        ), today).map { it.id }
        assertEquals(listOf("overdue", "today", "late-urgent", "old", "late-normal"), ids)
    }

    @Test fun mergeKeepsSavedOrderDropsMissingAndAppendsNew() {
        val rows = listOf(row("a"), row("b"), row("c", priority = "urgent"))
        assertEquals(listOf("b", "a", "c"), mergeQueueOrder(listOf("b", "gone", "a", "b"), rows, today))
        assertEquals(listOf("c", "a", "b"), mergeQueueOrder(null, rows, today))
        assertEquals(listOf("c", "a", "b"), mergeQueueOrder(emptyList(), rows, today))
    }

    @Test fun filtersCombine() {
        val rows = listOf(
            row("a", status = "awaiting_quote", priority = "urgent"), row("b", status = "working_on", due = "2026-10-20"),
            row("c", status = "working_on", due = "2026-10-30"), row("d", status = "working_on", due = "2026-10-01", priority = "low"),
        )
        assertEquals(4, filterQueueRows(rows, QueueFilters(), today).size)
        assertEquals(listOf("b", "c", "d"), filterQueueRows(rows, QueueFilters(statuses = setOf("working_on")), today).map { it.id })
        assertEquals(listOf("a"), filterQueueRows(rows, QueueFilters(priorities = setOf("urgent")), today).map { it.id })
        assertEquals(listOf("b", "d"), filterQueueRows(rows, QueueFilters(dueTodayOnly = true), today).map { it.id })
        assertEquals(listOf("d"), filterQueueRows(rows, QueueFilters(statuses = setOf("working_on"), priorities = setOf("low"), dueTodayOnly = true), today).map { it.id })
    }

    @Test fun filterCountMatchesWebBadge() {
        assertFalse(QueueFilters().active)
        val f = QueueFilters(setOf("go_ahead", "working_on"), setOf("urgent"), true)
        assertEquals(4, f.count)
        assertTrue(f.active)
    }

    @Test fun toggleAndMoveHelpers() {
        assertEquals(setOf("a", "b"), setOf("a").toggled("b"))
        assertEquals(setOf("a"), setOf("a", "b").toggled("b"))
        assertEquals(listOf("c", "a", "b"), moveToFront(listOf("a", "b", "c"), "c"))
        assertEquals(listOf("b", "c", "a"), moveToBack(listOf("a", "b", "c"), "a"))
    }

    @Test fun epochParsesTheShapesTheApiReturns() {
        val z = queueEpochMillis("2026-10-08T00:00:00Z")
        assertTrue(z > 0)
        assertEquals(z, queueEpochMillis("2026-10-08T00:00:00+00:00"))
        assertEquals(z, queueEpochMillis("2026-10-08T00:00:00"))
        assertEquals(z, queueEpochMillis("2026-10-08"))
        assertEquals(0L, queueEpochMillis(null))
        assertEquals(0L, queueEpochMillis("garbage"))
    }

    @Test fun watchEligibleJobsFollowQueueOrder() {
        fun job(id: String, status: String, due: String? = null, priority: String = "normal") = RepairJobRead(
            id = id, tenantId = "t", watchId = "w", jobNumber = id, title = id, description = null,
            status = status, priority = priority, customerName = null, createdAt = "2026-10-08T00:00:00Z", collectionDate = due,
        )
        val ids = queueEligibleJobs(listOf(
            job("W-3", "working_on"), job("W-2", "go_ahead", "2026-10-30"), job("W-1", "awaiting_quote", "2026-10-10"),
            job("W-4", "collected"), job("W-5", "no_go"), job("W-6", "service"), job("W-7", "working_on", priority = "urgent"),
        ), today).map { it.id }
        assertEquals(listOf("W-1", "W-7", "W-3", "W-2"), ids)
    }
}
