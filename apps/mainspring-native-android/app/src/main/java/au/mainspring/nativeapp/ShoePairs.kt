package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ShoeRead
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import com.google.gson.JsonObject

/** PATCH body for shoe-repair-jobs/shoes/{id}; trimmed strings, matching the web EditTicketModal (blank clears the field). */
fun shoeUpdateBody(type: String, brand: String, colour: String, notes: String): JsonObject = JsonObject().apply {
    addProperty("shoe_type", type.trim()); addProperty("brand", brand.trim()); addProperty("color", colour.trim()); addProperty("description_notes", notes.trim())
}

/** A new pair needs at least one of type, brand or colour (web AddPairModal). */
fun canAddNewPair(type: String, brand: String, colour: String) = type.isNotBlank() || brand.isNotBlank() || colour.isNotBlank()

/** The customer's shoes not already on this job (primary or extra). */
fun availableCustomerShoes(all: List<ShoeRead>, job: ShoeRepairJobRead?): List<ShoeRead> {
    if(job == null) return emptyList()
    val used = setOfNotNull(job.shoeId, job.shoe?.id) + job.extraShoes.orEmpty().map { it.shoeId }
    return all.filter { it.id !in used }
}
