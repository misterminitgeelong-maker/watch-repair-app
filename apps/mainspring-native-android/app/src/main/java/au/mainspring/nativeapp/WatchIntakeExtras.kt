package au.mainspring.nativeapp

import com.google.gson.annotations.SerializedName
import retrofit2.http.GET

data class JobTemplate(val id: String, val label: String, val module: String, val title: String,
    @SerializedName("pre_quote_cents") val preQuoteCents: Int)
interface WatchWorkflowApi { @GET("v1/job-templates") suspend fun templates(): List<JobTemplate> }

val WATCH_CONDITION_CHECKLIST = listOf("scratches", "dents", "cracked crystal", "crown missing", "strap damage")

/** Preserve the operator's own notes; the checklist adds a readable, stable statement to the watch condition. */
fun watchConditionNotes(notes: String, checklist: String): String? {
    val selected = checklist.split('|').filter { it in WATCH_CONDITION_CHECKLIST }.distinct()
    return listOfNotNull(notes.trim().takeIf(String::isNotEmpty), selected.takeIf { it.isNotEmpty() }?.joinToString(", ")?.let { "Condition: $it" })
        .joinToString("\n").ifBlank { null }
}
