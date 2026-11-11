package au.mainspring.nativeapp

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.test.espresso.Espresso
import au.mainspring.nativeapp.ui.screens.*
import com.google.gson.Gson
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Capture-only routes. Every list/model is loaded from the disposable real backend.
 * Preparation opens tabs and forms and fills local drafts; it never submits messages,
 * changes a status, consumes stock, creates a shop or sends a notification. */
fun communityReviewCases(data: ReviewData): List<ReviewCase> = buildList {
    val shoeJob = data.communityId("shoeJob", "shoe_job_id")
    val customer = data.communityId("customer", "customer_id")
    val network = data.communityId("network", "network_id")
    val conversation = data.communityId("conversation", "conversation_id")
    val engravingEvent = data.communityId("engravingEvent", "engraving_event_id")
    fun capture(id: String, title: String, group: String, prepare: (ComposeContentTestRule) -> Unit = {}, content: @Composable () -> Unit) {
        add(ReviewCase("community-$id", title, group, content, prepare))
    }
    fun shoeDirectory(): @Composable () -> Unit = { ShoeJobsScreen({}, {}, {}, onOpenQueue = {}) }
    fun shoeDetail(tab: String = "overview"): @Composable () -> Unit = {
        ShoeJobDetailScreen(shoeJob, data.baseUrl, {}, {}, {}, initialTab = tab)
    }
    fun detailReady(rule: ComposeContentTestRule) { rule.communityTag("tab-overview") }
    fun detailMenu(rule: ComposeContentTestRule, label: String) {
        detailReady(rule); rule.communityTag("detail-menu").performScrollTo().performClick(); rule.communityText(label).performClick()
    }

    capture("shoe-directory", "Shoe Repairs · directory and filters", "Shoe repairs", content = shoeDirectory())
    capture("shoe-cards", "Shoe Repairs · active job cards", "Shoe repairs", prepare = { rule ->
        rule.communityScroll(hasText("Arizona footbed replacement (Demo)", substring = true))
    }, content = shoeDirectory())
    capture("shoe-board", "Shoe Repairs · board", "Shoe repairs", prepare = { rule ->
        rule.communityTag("view-board").performScrollTo().performClick()
        rule.communityTag("zoom-board-shoe").performScrollTo()
        // HoldMenu merges the card's semantics into its clickable parent. Scroll
        // the actual card in the unmerged tree after bringing the board into view.
        rule.waitUntil(20_000) { rule.onAllNodesWithTag("board-card-$shoeJob", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("board-card-$shoeJob", useUnmergedTree = true).performScrollTo().assertIsDisplayed()
    }, content = shoeDirectory())
    capture("shoe-catalogue-tab", "Shoe Repairs · Services tab", "Shoe repairs", prepare = { rule ->
        rule.communityTag("tab-catalogue").performScrollTo().performClick()
    }, content = shoeDirectory())
    capture("shoe-combos", "Shoe Repairs · pricing combos and guarantee", "Shoe repairs", prepare = { rule ->
        rule.communityTag("combos-toggle").performScrollTo().performClick()
    }, content = shoeDirectory())
    capture("shoe-services", "Shoe services catalogue", "Shoe repairs") { ShoeServicesScreen({}) }
    listOf("overview" to "Details", "work" to "Work Logs", "money" to "Money", "messages" to "Messages", "attachments" to "Attachments").forEach { (tab, label) ->
        capture("shoe-detail-$tab", "Shoe repair · $label", "Shoe repairs", prepare = { detailReady(it) }, content = shoeDetail(tab))
    }
    capture("shoe-pairs", "Shoe repair · model, purchase and warranty", "Shoe repairs", prepare = { rule ->
        detailReady(rule); rule.communityScroll(hasTestTag("edit-pair-1"))
    }, content = shoeDetail())
    capture("shoe-parts", "Shoe repair · suggested and used parts", "Shoe repairs", prepare = { rule ->
        detailReady(rule); rule.communityScroll(hasText("Parts", substring = false, ignoreCase = true))
    }, content = shoeDetail())
    capture("shoe-history", "Shoe repair · history", "Shoe repairs", prepare = { rule ->
        detailReady(rule); rule.communityScroll(hasText("History", substring = false, ignoreCase = true))
    }, content = shoeDetail())
    capture("shoe-edit-pair", "Shoe repair · edit pair and purchase fields", "Shoe repairs", prepare = { rule ->
        detailReady(rule); rule.communityTag("edit-pair-1").performScrollTo().performClick(); rule.communityText("Edit pair")
        rule.communityTag("shoe-purchase-search")
    }, content = shoeDetail())
    capture("shoe-purchase-lookup", "Shoe repair · original purchase lookup", "Shoe repairs", prepare = { rule ->
        detailReady(rule); rule.communityTag("edit-pair-1").performScrollTo().performClick()
        rule.communityTag("shoe-purchase-search").performScrollTo().performTextInput("DEMO")
        rule.communityText("Search purchases").performScrollTo().performClick()
        rule.waitUntil(20_000) { rule.onAllNodesWithText("DEMO-RECEIPT-001", substring = true).fetchSemanticsNodes().isNotEmpty() }
        communityHideKeyboard()
    }, content = shoeDetail())
    capture("shoe-add-pair", "Shoe repair · add another pair", "Shoe repairs", prepare = { rule ->
        detailReady(rule); rule.communityText("Add pair").performScrollTo().performClick()
    }, content = shoeDetail())
    capture("shoe-add-services", "Shoe repair · add services", "Shoe repairs", prepare = { rule ->
        detailReady(rule); rule.communityText("Add services").performScrollTo().performClick()
    }, content = shoeDetail("work"))
    capture("shoe-status", "Shoe repair · change status and customer note", "Shoe repairs", prepare = { detailMenu(it, "Change status") }, content = shoeDetail())
    capture("shoe-send-quote", "Shoe repair · quote delivery confirmation", "Shoe repairs", prepare = { detailMenu(it, "Send quote to customer") }, content = shoeDetail())
    capture("shoe-notify", "Shoe repair · customer notification choices", "Shoe repairs", prepare = { detailMenu(it, "Notify customer") }, content = shoeDetail())
    capture("shoe-note", "Shoe repair · internal note editor", "Shoe repairs", prepare = { detailMenu(it, "Add note") }, content = shoeDetail())
    capture("shoe-files", "Shoe repair · photo and file tools", "Shoe repairs") { JobPhotosScreen("shoe-repair-jobs", shoeJob, {}) }
    (0..3).forEach { step ->
        val label = listOf("Customer", "Pairs, services and purchase", "Job details", "Intake photos")[step]
        capture("shoe-intake-$step", "New shoe repair · $label", "Shoe repairs") { CommunityShoeIntake(data, customer, step) }
    }
    capture("shoe-intake-purchase", "New shoe repair · purchase and warranty information", "Shoe repairs", prepare = { rule ->
        // MAINSPRING's field labels are exposed as content descriptions rather
        // than text nodes, including when the populated field is off screen.
        rule.communityScroll(hasContentDescription("Purchase date (DD/MM/YYYY)"))
    }) { CommunityShoeIntake(data, customer, 1) }

    capture("stock-overview", "Parts stock · incoming transfers and levels", "Parts stock") { PartsStockScreen({}) }
    capture("stock-count", "Parts stock · add stock or set exact count", "Parts stock", prepare = { rule ->
        rule.communityScroll(hasTestTag("stock-sku"))
    }) { PartsStockScreen({}) }
    capture("stock-transfer", "Parts stock · send transfer form", "Parts stock", prepare = { rule ->
        rule.communityScroll(hasTestTag("transfer-sku"))
    }) { PartsStockScreen({}) }
    capture("stock-history", "Parts stock · transfer history", "Parts stock", prepare = { rule ->
        rule.communityScroll(hasText("TRANSFER HISTORY", substring = false))
    }) { PartsStockScreen({}) }

    fun engraving(open: Boolean = true): @Composable () -> Unit = {
        val model: EngravingViewModel = viewModel()
        LaunchedEffect(open, engravingEvent) { if(open) model.open(engravingEvent) }
        EngravingScreen({}, model)
    }
    fun engravingReady(rule: ComposeContentTestRule) { rule.communityText("Walk-up order") }
    capture("engraving-events", "Medal engraving · event list", "Medal engraving", content = engraving(false))
    capture("engraving-new", "Medal engraving · new event form", "Medal engraving", prepare = { rule ->
        rule.communityText("New engraving event").performClick()
    }, content = engraving(false))
    capture("engraving-queue", "Medal engraving · event queue", "Medal engraving", prepare = { engravingReady(it) }, content = engraving())
    capture("engraving-current", "Medal engraving · now engraving", "Medal engraving", prepare = { rule ->
        engravingReady(rule); rule.communityScroll(hasTestTag("engraving-medal-done"))
    }, content = engraving())
    capture("engraving-walk-up", "Medal engraving · walk-up order and preview", "Medal engraving", prepare = { rule ->
        engravingReady(rule); rule.communityText("Walk-up order").performClick()
        rule.communityText("Athlete’s name").performScrollTo().performTextInput("Avery Lee (Demo)")
        rule.communityText("Second line").performScrollTo().performTextInput("100 metres")
        communityHideKeyboard()
    }, content = engraving())
    capture("engraving-settings", "Medal engraving · event settings", "Medal engraving", prepare = { rule ->
        engravingReady(rule); rule.communityText("Event settings").performScrollTo().performClick()
    }, content = engraving())
    capture("engraving-qr", "Medal engraving · customer order QR sign", "Medal engraving", prepare = { rule ->
        engravingReady(rule); rule.communityText("QR sign").performClick()
    }, content = engraving())
    capture("engraving-ready", "Medal engraving · ready for pickup", "Medal engraving", prepare = { rule ->
        engravingReady(rule); rule.communityScroll(hasText("Ready", substring = false)); rule.communityText("Ready").performClick()
        rule.communityScroll(hasText("Collected", substring = false))
    }, content = engraving())
    capture("engraving-orders", "Medal engraving · all orders", "Medal engraving", prepare = { rule ->
        engravingReady(rule); rule.communityScroll(hasText("All", substring = false)); rule.communityText("All").performClick()
    }, content = engraving())
    capture("engraving-edit", "Medal engraving · edit order", "Medal engraving", prepare = { rule ->
        engravingReady(rule); rule.communityScroll(hasText("Edit", substring = false)); rule.communityText("Edit").performClick()
    }, content = engraving())
    capture("engraving-export", "Medal engraving · laser export formats", "Medal engraving", prepare = { rule ->
        engravingReady(rule); rule.communityScroll(hasText("Save laser file", substring = false))
    }, content = engraving())

    fun messages(tab: String = "chats", hub: String? = null, direct: Boolean = false): @Composable () -> Unit = {
        NetworkMessagesScreen({}, conversation = conversation.takeIf { direct }, initialTab = tab, network = network, hub = hub)
    }
    capture("messages-chats", "Messages · conversations", "Network messages", content = messages())
    capture("messages-directory", "Messages · shop directory and filters", "Network messages", content = messages("directory"))
    capture("messages-announcements", "Messages · announcements and confirmation receipts", "Network messages", content = messages("announcements"))
    capture("messages-hubs", "Messages · state hubs", "Network messages", content = messages("hubs"))
    capture("messages-hub-thread", "Messages · Victoria state conversation", "Network messages", prepare = { it.communityTag("network-draft") }, content = messages(hub = "VIC"))
    capture("messages-hub-reply", "Messages · hub reply composer", "Network messages", prepare = { rule ->
        rule.communityTag("network-draft")
        rule.communityScroll(hasText("Reply", substring = false)); rule.communityText("Reply").performClick()
        rule.communityTag("network-draft").performTextInput("Demo: we can arrange a parts transfer."); communityHideKeyboard()
    }, content = messages(hub = "VIC"))
    capture("messages-direct-thread", "Messages · private shop conversation", "Network messages", prepare = { it.communityTag("network-draft") }, content = messages(direct = true))
    capture("messages-receipts", "Messages · announcement receipt report", "Network messages", prepare = { rule ->
        rule.communityScroll(hasText("View receipts", substring = false)); rule.communityText("View receipts").performClick()
        rule.communityText("Announcement receipts")
    }, content = messages("announcements"))

    capture("my-shops", "My Shops · linked locations", "My Shops") { MyShopsScreen({}, {}) }
    capture("my-shops-link", "My Shops · link existing shop form", "My Shops", prepare = { rule ->
        rule.communityText("Add Shop").performClick()
    }) { MyShopsScreen({}, {}) }
    capture("my-shops-create", "My Shops · new shop form and starting plan", "My Shops", prepare = { rule ->
        rule.communityText("Add Shop").performClick(); rule.communityText("Create new").performClick()
    }) { MyShopsScreen({}, {}) }
    capture("my-shops-usage", "My Shops · booking usage and activity", "My Shops", prepare = { rule ->
        rule.communityScroll(hasText("SHOP BOOKING USAGE", substring = false))
    }) { MyShopsScreen({}, {}) }
}

private fun ReviewData.communityId(vararg keys: String): String = keys.firstNotNullOfOrNull { ids[it] }
    ?: error("Missing community screenshot fixture: ${keys.joinToString()}")

/** These are ordinary persisted intake fields, not fake responses or production fixture hooks. */
@Composable private fun CommunityShoeIntake(data: ReviewData, customer: String, step: Int) {
    val factory = object: ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T {
            val purchase = LocalDate.now(ZoneId.of(TokenStore.calendarTimezone())).minusDays(30).format(DateTimeFormatter.ofPattern("dd/MM/uuuu"))
            val fields = mapOf("step" to "$step", "customerMode" to "existing", "customerId" to customer, "count" to "1",
                "pair.0.type" to "Birkenstocks", "pair.0.brand" to "Birkenstock", "pair.0.color" to "Tan", "pair.0.condition" to "Worn footbed and buckle (Demo)",
                "pair.0.model" to "Arizona", "pair.0.size" to "41", "pair.0.purchaseDate" to purchase,
                "pair.0.purchaseStore" to "Geelong (Demo)", "pair.0.purchaseRef" to "DEMO-RECEIPT-001",
                "title" to "Arizona footbed replacement (Demo)", "description" to "Synthetic intake draft for screen review", "deposit" to "20.00", "salesperson" to "Native QA Owner")
            return ShoeIntakeViewModel(SavedStateHandle(mapOf("draft" to Gson().toJson(fields)))) as T
        }
    }
    val model: ShoeIntakeViewModel = viewModel(key = "community-intake-$step", factory = factory)
    ShoeIntakeScreen({}, data.baseUrl, {}, model)
}

private fun ComposeContentTestRule.communityText(text: String, substring: Boolean = false): SemanticsNodeInteraction {
    waitUntil(20_000) { onAllNodesWithText(text, substring = substring, ignoreCase = true).fetchSemanticsNodes().any { !it.config.contains(SemanticsProperties.Disabled) } }
    return onAllNodesWithText(text, substring = substring, ignoreCase = true).onFirst()
}
private fun ComposeContentTestRule.communityTag(tag: String): SemanticsNodeInteraction {
    waitUntil(20_000) { onAllNodesWithTag(tag).fetchSemanticsNodes().any { !it.config.contains(SemanticsProperties.Disabled) } }
    return onAllNodesWithTag(tag).onFirst()
}
private fun ComposeContentTestRule.communityScroll(matcher: SemanticsMatcher) {
    waitUntil(20_000) {
        runCatching {
            val lazy = onAllNodes(SemanticsMatcher.keyIsDefined(SemanticsActions.ScrollToIndex))
            if(lazy.fetchSemanticsNodes().isNotEmpty()) lazy.onFirst().performScrollToNode(matcher)
            else onAllNodes(matcher).onFirst().performScrollTo()
            onAllNodes(matcher).fetchSemanticsNodes().isNotEmpty()
        }.getOrDefault(false)
    }
    waitForIdle()
}
private fun communityHideKeyboard() { runCatching { Espresso.closeSoftKeyboard() } }
