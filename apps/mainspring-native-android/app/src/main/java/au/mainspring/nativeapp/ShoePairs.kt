package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.ShoeRead
import au.mainspring.nativeapp.api.ShoeRepairJobRead
import com.google.gson.JsonObject

/** PATCH body for shoe-repair-jobs/shoes/{id}; trimmed strings, matching the web EditTicketModal (blank clears the field). */
fun shoeUpdateBody(type: String, brand: String, colour: String, notes: String): JsonObject = JsonObject().apply {
    addProperty("shoe_type", type.trim()); addProperty("brand", brand.trim()); addProperty("color", colour.trim()); addProperty("description_notes", notes.trim())
}

/** Purchase information is editable; warranty is calculated by the server from the saved purchase date. */
data class ShoePurchaseDetails(val model: String = "", val size: String = "", val date: String = "", val store: String = "", val reference: String = "")
fun shoeUpdateBody(type: String, brand: String, colour: String, notes: String, purchase: ShoePurchaseDetails): JsonObject =
    shoeUpdateBody(type, brand, colour, notes).apply {
        addProperty("model_name", purchase.model.trim().ifBlank { null }); addProperty("size", purchase.size.trim().ifBlank { null })
        addProperty("purchase_date", collectionDateIso(purchase.date))
        addProperty("purchase_store", purchase.store.trim().ifBlank { null }); addProperty("purchase_ref", purchase.reference.trim().ifBlank { null })
    }

fun shoeWarrantyLabel(shoe: ShoeRead): String? = when(shoe.warrantyStatus) {
    "in_warranty" -> "In warranty" + shoe.warrantyExpiresOn?.let { " until ${au.mainspring.nativeapp.ui.formatShopDate(it)}" }.orEmpty()
    "expired" -> "Out of warranty" + shoe.warrantyExpiresOn?.let { " (ended ${au.mainspring.nativeapp.ui.formatShopDate(it)})" }.orEmpty()
    else -> null
}

/** A new pair needs at least one of type, brand or colour (web AddPairModal). */
fun canAddNewPair(type: String, brand: String, colour: String) = type.isNotBlank() || brand.isNotBlank() || colour.isNotBlank()

/** The customer's shoes not already on this job (primary or extra). */
fun availableCustomerShoes(all: List<ShoeRead>, job: ShoeRepairJobRead?): List<ShoeRead> {
    if(job == null) return emptyList()
    val used = setOfNotNull(job.shoeId, job.shoe?.id) + job.extraShoes.orEmpty().map { it.shoeId }
    return all.filter { it.id !in used }
}
