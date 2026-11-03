package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.*

interface ShoeIntakeGateway {
    suspend fun customer(body: CustomerCreate): String
    suspend fun shoe(body: ShoeCreate): String
    suspend fun job(body: ShoeJobCreate): String
    suspend fun link(jobId: String, shoeId: String)
    suspend fun append(jobId: String, items: List<ShoeItemCreate>)
}

suspend fun createShoeIntake(fields: MutableMap<String, String>, catalogue: List<ShoeCatalogueItem>,
    gateway: ShoeIntakeGateway, checkpoint: (String, String) -> Unit): String {
    fun f(key: String) = fields[key].orEmpty().trim()
    fun save(key: String, value: String): String { fields[key] = value; checkpoint(key, value); return value }
    val count = f("count").toIntOrNull() ?: 1
    require(count in 1..15) { "Choose between 1 and 15 pairs." }
    require(f("customerId").isNotBlank() || f("name").isNotBlank()) { "Select a customer or enter their name." }
    val deposit = dollarsToCentsChecked(f("deposit")); val date = collectionDateIso(f("collection"))
    val priority = f("priority").ifBlank { "normal" }; val status = f("status").ifBlank { "awaiting_go_ahead" }
    require(priority in listOf("low", "normal", "high", "urgent")) { "Invalid priority." }
    require(status in listOf("awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on")) { "Invalid initial status." }
    val allItems = (0 until count).map { i ->
        val keys = f("pair.$i.services").split('|').filter(String::isNotBlank)
        keys.map { key ->
            val item = catalogue.firstOrNull { it.key == key } ?: error("A selected service is unavailable. Reload the catalogue.")
            val quantity = f("pair.$i.quantity.$key").ifBlank { "1" }.toDoubleOrNull() ?: error("Enter a valid quantity.")
            require(quantity.isFinite() && quantity > 0 && quantity <= 10_000) { "Quantity must be between 0 and 10,000." }
            val price = f("pair.$i.price.$key").takeIf(String::isNotBlank)?.let(::dollarsToCentsChecked) ?: item.priceCents
            val note = f("pair.$i.note.$key")
            ShoeItemCreate(item.key, item.groupId, item.name, item.pricingType, price, quantity,
                if(count > 1) "Pair ${i + 1}" + if(note.isNotBlank()) " - $note" else "" else note.ifBlank { null })
        }
    }
    require(f("uncertain").isBlank()) { "A previous save has an unknown result. Check the shop records before retrying." }
    suspend fun acknowledged(key: String, action: suspend () -> String): String {
        save("uncertain", key)
        try { val result = action(); save(key, result); save("hasAcknowledgement", "true"); save("uncertain", ""); return result }
        catch(e: retrofit2.HttpException) { if(e.code() in 400..499) save("uncertain", ""); throw e }
    }
    val customer = f("customerId").ifBlank { acknowledged("customerId") {
        gateway.customer(CustomerCreate(f("name"), f("phone").ifBlank { null }, f("email").ifBlank { null })) } }
    val shoes = (0 until count).map { i -> f("pair.$i.id").ifBlank { acknowledged("pair.$i.id") {
        gateway.shoe(ShoeCreate(customer, f("pair.$i.type").ifBlank { null }, f("pair.$i.brand").ifBlank { null },
            f("pair.$i.color").ifBlank { null }, f("pair.$i.condition").ifBlank { null })) } } }
    val title = f("title").ifBlank { allItems.flatten().map { it.name }.distinct().joinToString(", ").ifBlank { "Shoe repair ($count pairs)" } }
    val job = f("jobId").ifBlank { acknowledged("jobId") {
        gateway.job(ShoeJobCreate(shoes.first(), title, f("description").ifBlank { null },
            priority, status, f("salesperson").ifBlank { null },
            date, deposit, allItems.first(), f("accountId").ifBlank { null })) } }
    for(i in 1 until count) {
        if(f("pair.$i.linked").isBlank()) acknowledged("pair.$i.linked") { gateway.link(job, shoes[i]); "yes" }
        if(allItems[i].isNotEmpty() && f("pair.$i.itemsSaved").isBlank()) acknowledged("pair.$i.itemsSaved") { gateway.append(job, allItems[i]); "yes" }
    }
    return job
}
