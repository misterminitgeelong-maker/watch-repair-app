package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.CustomerRead
import au.mainspring.nativeapp.api.RepairJobRead
import org.junit.Assert.assertEquals
import org.junit.Test

class QuoteAndMergePickerTest {
    private fun job(id: String, number: String, title: String, customer: String?, status: String = "awaiting_quote") =
        RepairJobRead(id = id, tenantId = "t", watchId = "w", jobNumber = number, title = title, description = null, status = status,
            priority = "normal", customerName = customer, createdAt = "2026-10-01T00:00:00Z")
    private fun customer(id: String, name: String, phone: String? = null, email: String? = null) =
        CustomerRead(id = id, tenantId = "t", fullName = name, email = email, phone = phone, address = null, notes = null, createdAt = "2026-10-01T00:00:00Z")

    private val jobs = listOf(job("1", "W100", "Omega service", "Avery Smith"), job("2", "W101", "Strap swap", "Bob Jones"),
        job("3", "W102", "Seiko crystal", "Avery Smith", status = "collected"))

    @Test fun quotableJobsDropsFinishedJobsAndMatchesNumberTitleOrCustomer() {
        assertEquals(listOf("1", "2"), quotableJobs(jobs, "").map { it.id })
        assertEquals(listOf("2"), quotableJobs(jobs, "w101").map { it.id })
        assertEquals(listOf("1"), quotableJobs(jobs, " omega ").map { it.id })
        assertEquals(listOf("1"), quotableJobs(jobs, "avery").map { it.id })
        assertEquals(emptyList<String>(), quotableJobs(jobs, "zzz").map { it.id })
    }

    private val people = listOf(customer("a", "Avery Smith", "0412 345 678", "avery@example.com"), customer("b", "Avery Smyth", "0412345678"), customer("c", "Bob Jones", email = "bob@example.com"))

    @Test fun mergeCandidatesMatchesNamePhoneAndEmailAndExcludesKept() {
        assertEquals(listOf("a", "b", "c"), mergeCandidates(people, "").map { it.id })
        assertEquals(listOf("b"), mergeCandidates(people, "avery", excludeId = "a").map { it.id })
        assertEquals(listOf("a", "b"), mergeCandidates(people, "0412345678").map { it.id })
        assertEquals(listOf("c"), mergeCandidates(people, "BOB@").map { it.id })
    }
}
