package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.DashboardWidgetsResponse

/**
 * Where the dashboard "Start follow-up sweep" button goes first, in the web's priority order
 * (DashboardPage followUpRoute): stale go-aheads, quotes unanswered 7+ days, unpaid invoices, past collection.
 * Returns an app route key ("watch_jobs", "quotes", "invoices") or null when nothing needs chasing.
 */
fun followUpSweepTarget(w: DashboardWidgetsResponse?): String? = when {
    w == null -> null
    w.overdueJobsCount > 0 -> "watch_jobs"
    w.quotesPending7dCount > 0 -> "quotes"
    w.overdueInvoicesCount > 0 -> "invoices"
    w.overdueCollectionCount > 0 -> "watch_jobs"
    else -> null
}

/** Quotes still needing action: drafts plus sent (web `quotesPendingCount`). */
fun quotesPendingCount(quotesByStatus: Map<String, Int>): Int = (quotesByStatus["draft"] ?: 0) + (quotesByStatus["sent"] ?: 0)
