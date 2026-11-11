package au.mainspring.nativeapp

import androidx.compose.runtime.Composable
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import au.mainspring.nativeapp.ui.screens.*

/** Actual API-backed screens. Preparation only changes unsaved UI state; it never submits
 * an intake, payment, message, work log, quote, status transition or editor. */
fun watchReviewCases(data: ReviewData): List<ReviewCase> = buildList {
    fun fixture(vararg keys: String): String = keys.firstNotNullOfOrNull { data.ids[it] }
        ?: error("Missing screenshot fixture: ${keys.joinToString()}")
    val customer = fixture("customer", "customer_id")
    val job = fixture("watchJob", "watch_job_id", "repair_job_id")
    val watch = fixture("watch", "watch_id")
    val quote = fixture("watchQuote", "watch_quote_id", "quote_id")
    val invoice = fixture("watchInvoice", "watch_invoice_id", "invoice_id")
    fun capture(id: String, title: String, group: String = "Watch repairs", prepare: (ComposeContentTestRule) -> Unit = {}, content: @Composable () -> Unit) {
        add(ReviewCase("watch-$id", title, group, content, prepare))
    }
    fun detail(tab: String = "overview"): @Composable () -> Unit = {
        JobDetailScreen(job, data.baseUrl, {}, {}, {}, {}, {}, initialTab = tab)
    }
    fun directory(): @Composable () -> Unit = { JobsScreen({}, {}, onOpenQueue = {}, onLogWork = {}) }
    fun profile(): @Composable () -> Unit = {
        CustomerDetailScreen(customer, {}, {}, {}, {}, features = setOf("watch", "shoe", "auto_key"))
    }
    fun intake(selected: Boolean = false): @Composable () -> Unit = {
        WatchIntakeScreen(onBack = {}, apiBaseUrl = data.baseUrl, onOpenJob = {}, preselectedCustomerId = if(selected) customer else null)
    }
    fun jobQuotes(): @Composable () -> Unit = { JobQuotesScreen(job, {}, {}) }
    fun openMenu(rule: ComposeContentTestRule, action: String) {
        rule.watchReviewTag("detail-menu").performScrollTo().performClick()
        rule.watchReviewText(action).performScrollTo().performClick()
    }
    fun customerTab(rule: ComposeContentTestRule, label: String) {
        val text = hasText(label, substring = true, ignoreCase = true)
        rule.watchReveal(text)
        // Mainspring presents profile sections in a continuous page; Atelier uses tabs.
        val tab = text and hasClickAction()
        if(rule.onAllNodes(tab).fetchSemanticsNodes().isNotEmpty()) rule.onAllNodes(tab).onFirst().performClick()
    }
    fun intakeDetails(rule: ComposeContentTestRule) {
        rule.watchReviewText("New watch")
        rule.watchReviewText("Next →").performClick()
        rule.waitUntil(20_000) { rule.onAllNodesWithContentDescription("Job Title *").fetchSemanticsNodes().isNotEmpty() }
    }

    capture("directory", "Watch repairs · list", prepare = { it.watchReviewTag("view-list").performClick() }, content = directory())
    capture("board", "Watch repairs · board", prepare = { it.watchReviewTag("view-board").performClick() }, content = directory())
    capture("filters", "Watch repairs · filters", prepare = { it.watchReviewTag("filters-button").performClick() }, content = directory())
    capture("detail", "Watch job · details", prepare = { it.watchReviewText("Job ticket").performScrollTo() }, content = detail())
    capture("history", "Watch job · repair activity", prepare = { it.watchReviewText("Repair activity").performScrollTo() }, content = detail())
    capture("work", "Watch job · work logs", prepare = { it.watchReviewTag("log-work").performScrollTo() }, content = detail("work"))
    capture("shop-notes", "Watch job · shop notes", prepare = { it.watchReviewTag("edit-shop-notes").performScrollTo() }, content = detail("work"))
    capture("notes-editor", "Watch job · edit shop notes", prepare = { it.watchReviewTag("edit-shop-notes").performScrollTo().performClick() }, content = detail("work"))
    capture("activity-note", "Watch job · add activity note", prepare = { it.watchReviewText("Add activity note").performScrollTo().performClick() }, content = detail("work"))
    capture("attachments", "Watch job · attachments", content = detail("attachments"))
    capture("money", "Watch job · money", content = detail("money"))
    capture("messages-tab", "Watch job · messages", content = detail("messages"))
    capture("status-picker", "Watch job · status choices", prepare = { openMenu(it, "Change status") }, content = detail())
    capture("technician", "Watch job · assign technician", prepare = { openMenu(it, "Assign technician") }, content = detail())
    capture("movement-price", "Watch job · movement quote lookup", prepare = { openMenu(it, "Set quote from movement") }, content = detail())
    capture("edit", "Edit watch repair details") { CounterEditorScreen("repair-jobs", job, {}) }
    capture("work-log-form", "Watch job · work log form") { WorkLogsScreen(job, {}) }
    capture("photos", "Watch job · photo and file manager") { JobPhotosScreen("repair-jobs", job, {}) }
    capture("conversation", "Watch customer conversation") { MessageThreadScreen("repair-jobs", job, {}) }

    capture("intake-customer", "Watch intake · select customer", content = intake())
    capture("intake-new-customer", "Watch intake · new customer", prepare = { it.watchReviewText("New customer", substring = true).performClick() }, content = intake())
    capture("intake-watches", "Watch intake · watches", content = intake(true))
    capture("intake-condition", "Watch intake · movement and condition", prepare = { it.watchReviewText("Condition checklist").performScrollTo() }, content = intake(true))
    capture("intake-details", "Watch intake · job details and templates", prepare = ::intakeDetails, content = intake(true))
    capture("intake-repairs", "Watch intake · service selection", prepare = { rule ->
        intakeDetails(rule); rule.watchReviewText("Add custom service").performScrollTo()
    }, content = intake(true))
    capture("intake-photos", "Watch intake · front and back photos", prepare = { rule ->
        intakeDetails(rule)
        rule.onNodeWithContentDescription("Job Title *")
            .performTextReplacement("Battery replacement · review draft")
        rule.watchReviewText("Next →").performClick()
        rule.watchReviewText("Front and back photos", substring = true)
    }, content = intake(true))

    capture("customers", "Customers directory", "Customers") { CustomersScreen({}, {}) }
    capture("customer-profile", "Customer · contact and overview", "Customers", content = profile())
    capture("customer-jobs", "Customer · job history", "Customers", prepare = { it.watchReveal(hasText("Watch repair jobs", substring = true, ignoreCase = true)) }, content = profile())
    capture("customer-watches", "Customer · watches", "Customers", prepare = { customerTab(it, "Watches (") }, content = profile())
    capture("customer-orders", "Customer · orders", "Customers", prepare = { customerTab(it, "Orders") }, content = profile())
    capture("customer-account", "Customer · loyalty and account", "Customers", prepare = { customerTab(it, "Account") }, content = profile())
    capture("customer-contact", "Customer · contact information", "Customers", prepare = { it.watchReveal(hasText("Contact", ignoreCase = true)) }, content = profile())
    capture("customer-new", "New customer form", "Customers") { CustomerEditorScreen("", {}, {}) }
    capture("customer-edit", "Edit customer form", "Customers") { CustomerEditorScreen(customer, {}, {}) }
    capture("watch-new", "Add watch form", "Customers") { WatchEditorScreen(customer, "", {}, {}) }
    capture("watch-edit", "Edit watch form", "Customers") { WatchEditorScreen(customer, watch, {}, {}) }

    capture("quotes", "Quotes directory", "Quotes and invoices") { QuotesScreen({}, onBack = {}, onNewQuote = {}) }
    capture("quotes-filters", "Quote filters", "Quotes and invoices", prepare = { it.watchReviewTag("more-filters").performClick() }) { QuotesScreen({}, onBack = {}, onNewQuote = {}) }
    capture("quote-job-picker", "New quote · choose active repair", "Quotes and invoices", prepare = { it.watchReviewTag("new-quote").performClick() }) { QuotesScreen({}, onBack = {}, onNewQuote = {}) }
    capture("job-quotes", "Watch job · quote history", "Quotes and invoices", content = jobQuotes())
    capture("quote-composer", "Watch quote · typed line items", "Quotes and invoices", prepare = { it.watchReviewText("Description").performScrollTo() }, content = jobQuotes())
    capture("quote-detail", "Watch quote · totals and line items", "Quotes and invoices") { QuoteDetailScreen(quote, {}, {}) }
    capture("invoices", "Invoices directory", "Quotes and invoices") { InvoicesScreen({}, onBack = {}) }
    capture("invoice-detail", "Watch invoice · total and payment actions", "Quotes and invoices") { InvoiceDetailScreen(invoice, {}) }
    capture("invoice-payment", "Watch invoice · record payment form", "Quotes and invoices", prepare = { it.watchReveal(hasText("Record payment") and hasClickAction()).performClick() }) { InvoiceDetailScreen(invoice, {}) }
}

private fun ComposeContentTestRule.watchReviewText(text: String, substring: Boolean = false): SemanticsNodeInteraction {
    waitUntil(20_000) { onAllNodesWithText(text, substring = substring, ignoreCase = true).fetchSemanticsNodes().isNotEmpty() }
    return onAllNodesWithText(text, substring = substring, ignoreCase = true).onFirst()
}

private fun ComposeContentTestRule.watchReviewTag(tag: String): SemanticsNodeInteraction {
    waitUntil(20_000) { onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }
    return onAllNodesWithTag(tag).onFirst()
}

/** Lazy lists materialise only visible rows; regular scroll columns already expose their children. */
private fun ComposeContentTestRule.watchReveal(matcher: SemanticsMatcher): SemanticsNodeInteraction {
    waitUntil(20_000) { onAllNodes(hasScrollAction()).fetchSemanticsNodes().isNotEmpty() }
    if(onAllNodes(hasScrollToIndexAction()).fetchSemanticsNodes().isNotEmpty()) {
        onAllNodes(hasScrollToIndexAction()).onFirst().performScrollToNode(matcher)
    } else {
        waitUntil(20_000) { onAllNodes(matcher).fetchSemanticsNodes().isNotEmpty() }
        onAllNodes(matcher).onFirst().performScrollTo()
    }
    return onAllNodes(matcher).onFirst()
}
