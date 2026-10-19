package au.mainspring.nativeapp

import com.google.gson.Gson

/** Workflow rail step, mirroring the web `WorkflowRail` step lists. */
data class WorkflowStep(val key: String, val label: String, val statuses: List<String>)

val WATCH_WORKFLOW_STEPS: List<WorkflowStep> = listOf(
    WorkflowStep("received", "Received", listOf("awaiting_quote", "awaiting_customer_details")),
    WorkflowStep("quoted", "Quoted", listOf("awaiting_go_ahead", "quote_sent")),
    WorkflowStep("approved", "Approved", listOf("go_ahead", "awaiting_parts", "at_third_party_for_quoting", "third_party_quote_approved",
        "at_third_party_repairer", "parts_to_order", "sent_to_labanda", "quoted_by_labanda")),
    WorkflowStep("working", "In workshop", listOf("working_on", "service")),
    WorkflowStep("complete", "Completed", listOf("completed")),
    WorkflowStep("collected", "Collected", listOf("awaiting_collection", "collected")),
)

val SHOE_WORKFLOW_STEPS: List<WorkflowStep> = listOf(
    WorkflowStep("received", "Received", listOf("awaiting_quote", "awaiting_customer_details")),
    WorkflowStep("quoted", "Quoted", listOf("awaiting_go_ahead", "quote_sent")),
    WorkflowStep("working", "In work", listOf("go_ahead", "awaiting_parts", "working_on", "service")),
    WorkflowStep("complete", "Completed", listOf("completed")),
    WorkflowStep("collected", "Collected", listOf("awaiting_collection", "collected")),
)

/** Index of the step holding [status]; unknown statuses sit on the first step like the web. */
fun workflowStepIndex(steps: List<WorkflowStep>, status: String): Int =
    steps.indexOfFirst { status in it.statuses }.coerceAtLeast(0)

/** Web `STATUS_FLOW` for watch jobs: the single next sensible status (absent when terminal). */
private val WATCH_NEXT: Map<String, String> = mapOf(
    "awaiting_quote" to "awaiting_go_ahead", "awaiting_go_ahead" to "go_ahead", "go_ahead" to "working_on",
    "working_on" to "completed", "awaiting_parts" to "working_on",
    "parts_to_order" to "at_third_party_for_quoting", "sent_to_labanda" to "third_party_quote_approved",
    "quoted_by_labanda" to "at_third_party_for_quoting",
    "at_third_party_for_quoting" to "third_party_quote_approved", "third_party_quote_approved" to "at_third_party_repairer",
    "at_third_party_repairer" to "working_on", "service" to "completed",
    "completed" to "awaiting_collection", "awaiting_collection" to "collected",
)

private val SHOE_NEXT: Map<String, String> = mapOf(
    "awaiting_quote" to "awaiting_go_ahead", "awaiting_go_ahead" to "go_ahead", "go_ahead" to "working_on",
    "working_on" to "completed", "completed" to "awaiting_collection", "awaiting_collection" to "collected",
)

/** Suggested next status actions: the forward step first, then a clear alternative where one exists. */
fun suggestedWatchStatuses(status: String): List<String> = listOfNotNull(WATCH_NEXT[status]) + when (status) {
    "awaiting_go_ahead" -> listOf("no_go")
    "working_on" -> listOf("awaiting_parts")
    else -> emptyList()
}

fun suggestedShoeStatuses(status: String): List<String> = listOfNotNull(SHOE_NEXT[status]) + when (status) {
    "awaiting_go_ahead" -> listOf("no_go")
    else -> emptyList()
}

/** Colour band for days in shop: 0 normal, 1 warn (7+), 2 alert (14+). */
fun daysInShopSeverity(days: Int): Int = if (days >= 14) 2 else if (days >= 7) 1 else 0

fun daysInShopText(days: Int): String = if (days == 1) "1 day in shop" else "$days days in shop"

/** Ordered ids of the list the user opened a job from, so detail can step to the previous or next job. */
object JobNavContext {
    private val lists = HashMap<String, List<String>>()
    @Synchronized fun set(kind: String, ids: List<String>) { lists[kind] = ids }
    @Synchronized fun neighbors(kind: String, id: String): Pair<String?, String?> {
        val ids = lists[kind] ?: return null to null
        val i = ids.indexOf(id)
        if (i < 0) return null to null
        return ids.getOrNull(i - 1) to ids.getOrNull(i + 1)
    }
    @Synchronized fun position(kind: String, id: String): Pair<Int, Int>? {
        val ids = lists[kind] ?: return null
        val i = ids.indexOf(id)
        return if (i < 0) null else (i + 1) to ids.size
    }
    @Synchronized fun clear() { lists.clear() }
}

/** A named filter set on a watch or shoe job list. Unused fields stay at their defaults. */
data class SavedJobView(
    val name: String,
    val statusFilter: String? = null,
    val sort: String? = null,
    val minDaysInShop: Int? = null,
    val technicianId: String? = null,
    val board: Boolean = false,
    val showCompleted: Boolean = false,
    val query: String? = null,
    val costOutliers: Boolean = false,
)

/** Minimal string storage so the store is JVM-testable. */
interface ViewStorage {
    fun read(key: String): String?
    fun write(key: String, value: String)
}

/** Saved views per list kind ("watch" / "shoe"), scoped to the signed-in tenant and user by the storage key. */
class SavedViewsStore(private val storage: ViewStorage, private val scope: () -> String?) {
    private val gson = Gson()
    private fun key(kind: String): String? = scope()?.let { "saved_views:$it:$kind" }

    fun load(kind: String): List<SavedJobView> {
        val raw = key(kind)?.let(storage::read) ?: return emptyList()
        return try {
            gson.fromJson(raw, Array<SavedJobView>::class.java)?.filter { !it.name.isNullOrBlank() }.orEmpty()
        } catch (_: Exception) { emptyList() }
    }

    /** Adds or replaces (case-insensitive name match) a view and returns the new list. */
    fun save(kind: String, view: SavedJobView): List<SavedJobView> {
        val name = view.name.trim().take(MAX_NAME)
        if (name.isEmpty()) return load(kind)
        val next = (load(kind).filterNot { it.name.equals(name, ignoreCase = true) } + view.copy(name = name)).takeLast(MAX_VIEWS)
        key(kind)?.let { storage.write(it, gson.toJson(next)) }
        return next
    }

    fun delete(kind: String, name: String): List<SavedJobView> {
        val next = load(kind).filterNot { it.name.equals(name, ignoreCase = true) }
        key(kind)?.let { storage.write(it, gson.toJson(next)) }
        return next
    }

    companion object { const val MAX_NAME = 30; const val MAX_VIEWS = 12 }
}

/** Production store backed by the encrypted prefs, scoped by tenant and user. */
val appSavedViews: SavedViewsStore by lazy {
    SavedViewsStore(object : ViewStorage {
        override fun read(key: String) = TokenStore.loadScopedString(key)
        override fun write(key: String, value: String) = TokenStore.saveScopedString(key, value)
    }, { TokenStore.offlineScope() })
}
