package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*

interface IntakeGateway {
    suspend fun customer(body: CustomerCreate): String
    suspend fun watch(body: WatchCreate): String
    suspend fun job(body: RepairJobCreate): String
}

/** Validate every ticket before creating any resources, then checkpoint each acknowledgement. */
suspend fun createIntakeTickets(fields: MutableMap<String, String>, gateway: IntakeGateway,
    checkpoint: (String, String) -> Unit): List<String> {
    fun field(key: String) = fields[key].orEmpty().trim()
    fun remember(key: String, value: String): String { fields[key] = value; checkpoint(key, value); return value }
    val count = field("watchCount").toIntOrNull() ?: 1
    require(count in 1..5) { "Choose between one and five watches." }
    require(field("title").isNotEmpty()) { "Job title is required." }
    require(field("customerId").isNotEmpty() || field("name").isNotEmpty()) { "Select a customer or enter their name." }
    val deposit = dollarsToCentsChecked(field("deposit"))
    val preQuote = dollarsToCentsChecked(field("preQuote"))
    val collection = collectionDateIso(field("collection"))
    val priority = field("priority").ifBlank { "normal" }
    require(priority in listOf("low", "normal", "high", "urgent")) { "Invalid priority." }
    val status = field("status").ifBlank { "awaiting_quote" }
    require(status in listOf("awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on")) { "Invalid initial status." }
    // A transport failure can follow a committed POST. Never silently repeat an unacknowledged write.
    require(field("uncertainWrite").isEmpty()) { "A previous save has an unknown result. Check existing records and reconcile it before continuing." }
    suspend fun write(key: String, action: suspend () -> String): String {
        remember("uncertainWrite", key)
        try {
            val id = action()
            remember(key, id)
            remember("hasAcknowledgement", "true")
            remember("uncertainWrite", "")
            return id
        } catch (e: retrofit2.HttpException) {
            // Rejected requests did not acknowledge success. 5xx remains ambiguous.
            if (e.code() in 400..499) remember("uncertainWrite", "")
            throw e
        }
    }
    val customer = field("customerId").ifBlank {
        write("customerId") { gateway.customer(CustomerCreate(field("name"), field("phone").ifBlank { null },
            field("email").ifBlank { null }, field("address").ifBlank { null }, field("customerNotes").ifBlank { null })) }
    }
    return (0 until count).map { i ->
        val watchId = field("watch.$i.id").ifBlank {
            write("watch.$i.id") { gateway.watch(WatchCreate(customer,
                field("watch.$i.brand").ifBlank { null }, field("watch.$i.model").ifBlank { null },
                field("watch.$i.serial").ifBlank { null }, field("watch.$i.condition").ifBlank { null },
                field("watch.$i.movement").ifBlank { null })) }
        }
        field("job.$i.id").ifBlank {
            write("job.$i.id") { gateway.job(RepairJobCreate(watchId = watchId,
                customerAccountId = field("accountId").ifBlank { null },
                title = field("title") + if(count > 1) " (Watch ${i + 1} of $count)" else "",
                description = field("description").ifBlank { null }, priority = priority, status = status,
                salesperson = field("salesperson").ifBlank { null }, collectionDate = collection,
                depositCents = deposit, preQuoteCents = preQuote,
                jobNumberOverride = if(count == 1) field("ticketOverride").ifBlank { null } else null)) }
        }
    }
}
