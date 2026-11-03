package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.MOBILE_STATUS_PICKER
import com.google.gson.annotations.SerializedName

/** Body of POST auto-key-jobs/bulk-status (server limit: 1..100 jobs, 204 on success). */
data class BulkMobileStatus(@SerializedName("job_ids") val jobIds: List<String>, val status: String)

const val BULK_MAX_JOBS = 100

/** Toggle one job in the selection; selecting beyond the server limit is ignored. */
fun toggleBulkSelection(selected: Set<String>, id: String, max: Int = BULK_MAX_JOBS): Set<String> =
    if(id in selected) selected - id else if(selected.size >= max) selected else selected + id

/** Select every shown job up to the limit, or clear when they are all already selected. */
fun toggleSelectAll(selected: Set<String>, shownIds: List<String>, max: Int = BULK_MAX_JOBS): Set<String> =
    if(shownIds.isNotEmpty() && shownIds.all { it in selected }) selected - shownIds.toSet() else (selected + shownIds).take(max).toSet()

/** Selection limited to ids still on screen, so a filter change cannot send ids the user can no longer see. */
fun pruneBulkSelection(selected: Set<String>, shownIds: Collection<String>): Set<String> = selected.intersect(shownIds.toSet())

/** Only a known mobile status may be bulk-applied. */
fun isBulkStatus(status: String) = MOBILE_STATUS_PICKER.any { it.first == status }

/** Why a bulk request cannot be sent, or null when it can. */
fun bulkProblem(selected: Set<String>, status: String): String? = when {
    selected.isEmpty() -> "Select at least one job."
    selected.size > BULK_MAX_JOBS -> "You can change up to $BULK_MAX_JOBS jobs at a time."
    !isBulkStatus(status) -> "Choose a valid mobile job status."
    else -> null
}

/** Remembered list view (directory + focus), restored per user and shop like the web's saved auto-key view. */
data class MobileSavedView(val directory: String = "active", val focus: String? = null)

private val VALID_DIRECTORIES = setOf("active", "completed", "all")
private val VALID_FOCUS = setOf("today", "unscheduled", "unassigned", "needs_quote", "completed_unpaid")

/** Drops anything the list no longer understands so a stale saved view can never break the list. */
fun sanitizeSavedView(view: MobileSavedView?): MobileSavedView {
    val v = view ?: return MobileSavedView()
    return MobileSavedView(directory = v.directory.takeIf { it in VALID_DIRECTORIES } ?: "active", focus = v.focus?.takeIf { it in VALID_FOCUS })
}
