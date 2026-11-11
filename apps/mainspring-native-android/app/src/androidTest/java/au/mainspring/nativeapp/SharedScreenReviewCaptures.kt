package au.mainspring.nativeapp

import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.SemanticsActions
import au.mainspring.nativeapp.ui.*
import au.mainspring.nativeapp.ui.screens.*
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle

fun sharedReviewCases(data: ReviewData): List<ReviewCase> = buildList {
    val features = data.session.enabledFeatures.toSet()
    fun capture(id: String, title: String, content: @androidx.compose.runtime.Composable () -> Unit,
        prepare: (androidx.compose.ui.test.junit4.ComposeContentTestRule) -> Unit = {}) {
        add(ReviewCase("shared-$id", title, "Home and business", content, prepare))
    }
    capture("login", "Sign in", { LoginScreen(AuthUiState(), data.baseUrl) { _, _, _, _ -> } })
    fun shell(): @androidx.compose.runtime.Composable () -> Unit = {
        val auth: AuthViewModel = androidx.lifecycle.viewmodel.compose.viewModel(key = "review-auth")
        val current by auth.state.collectAsStateWithLifecycle()
        MainspringAppShell(current.sessionSummary ?: "${data.session.user.fullName} · ${data.session.user.role} · ${data.session.shopName.orEmpty()} · ${data.session.planCode} plan",
            data.baseUrl, {}, current.features.ifEmpty { features }, current.sites.ifEmpty { data.session.sites },
            current.activeSiteId ?: data.session.activeSiteId ?: data.session.tenantId, onSwitchSite = auth::switchSite,
            sessionError = current.error, subscriptionStatus = data.session.subscriptionStatus, trialEnd = data.session.trialEnd,
            sessionRole = current.role ?: data.session.user.role, onRefreshSession = auth::refreshSession)
    }
    capture("home", "Home · operations dashboard", shell())
    capture("shop-switch", "Current shop · switch between available shops", shell(), { rule ->
        check(data.session.sites.map { it.tenantId }.distinct().size > 1) { "The local screenshot account needs membership in two actual shops" }
        rule.waitUntil(10_000) { rule.onAllNodesWithTag("app-switch-shop").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("app-switch-shop").performClick()
        rule.onNodeWithText("Unsaved drafts remain tied to the shop and account that opened them.").assertExists()
        // Open the real shell chooser; selecting a shop would invoke the same AuthViewModel callback
        // as MainActivity. The capture deliberately stays on this reviewable choice screen.
    })
    capture("jobs", "All service lines · jobs", { AtelierJobsScreen(features, data.session.shopName, {}, {}) })
    capture("intake", "Choose a new job type", { NewIntakeScreen(features, {}, {}) })
    capture("more", "More · all tools", shell(), { rule -> rule.onNodeWithTag("nav-more").performClick() })
    capture("settings", "Appearance and device settings", shell(), { rule ->
        rule.onNodeWithTag("nav-more").performClick()
        rule.waitUntil(6000) { rule.onAllNodesWithText("Settings").fetchSemanticsNodes().isNotEmpty() }
        rule.onAllNodesWithText("Settings").onFirst().performClick()
    })
    listOf("toolsWorkshop" to "Workshop tools", "toolsMobile" to "Mobile tools", "toolsShop" to "Shop and team tools").forEach { (route, title) ->
        capture(route, title, { ToolsGridScreen(route, features, {}, {}) })
    }
    capture("inbox", "Inbox · notifications", { InboxScreen(onBack = {}, onOpenEntity = {}) })
    capture("hq-notice", "Message from Support Office", { HqAlertScreen(data.id("hqNotice"), {}) })
    capture("search", "Search jobs and customers", { SearchScreen({}, {}) })
    capture("search-results", "Search · sample results", { SearchScreen({}, {}) }, { rule ->
        rule.onAllNodes(hasSetTextAction()).onFirst().performTextInput("Demo")
    })
    capture("leads", "Leads hub", { LeadHubScreen({}, {}) })
    capture("reports", "Reports · overview", { PeriodReportsScreen({}) })
    capture("sales", "Reports · sales and activity", { ReportExtrasScreen({}) })
    capture("report-range", "Report date range", { ReportExtrasScreen({}) }, { rule ->
        rule.onAllNodesWithText("Custom", ignoreCase = true).onFirst().performClick()
    })
    capture("inventory", "Inventory", { StockScreen({}) })
    capture("queue-watch", "Repair queue · watch", { RepairQueueScreen({}, {}) })
    capture("queue-shoe", "Repair queue · shoe", { RepairQueueScreen({}, {}, initialLane = "shoe") })
    capture("orders", "Customer orders", { CustomerOrdersScreen({}) })
    capture("order-new", "New customer order", { CustomerOrdersScreen({}) }, { rule ->
        rule.waitUntil(6000) { rule.onAllNodesWithText("New order").fetchSemanticsNodes().isNotEmpty() }
        rule.onAllNodesWithText("New order").onFirst().performClick()
    })
    capture("business-accounts", "Business accounts", { BusinessAccountsScreen({}, {}) })
    capture("business-account", "Business account · statement", { BusinessAccountScreen(data.id("businessAccount"), {}, {}, { _, _ -> }) })
    capture("business-new", "New business account", { BusinessAccountEditorScreen("", {}, {}) })
    capture("business-edit", "Edit business account", { BusinessAccountEditorScreen(data.id("businessAccount"), {}, {}) })
    capture("counter-sale", "Point of sale · mobile quote", { CounterSaleScreen({}, { _, _ -> }) })
    capture("team", "Team and roles", { TeamScreen({}) })
    capture("team-new", "Add team member", { TeamScreen({}) }, { rule ->
        rule.waitUntil(6000) { rule.onAllNodesWithText("Add account").fetchSemanticsNodes().isNotEmpty() }
        rule.onAllNodesWithText("Add account").onFirst().performClick()
    })
    capture("shop-settings", "Shop settings · business identity", { OwnerSettingsScreen({}) })
    if(data.session.canManageIntegrations) capture("integrations", "HQ account · API keys and webhooks", { IntegrationsScreen({}) })
    else capture("integrations-denied", "API keys and webhooks · HQ account required", { IntegrationsScreen({}) }, { rule ->
        rule.onNodeWithText("HQ account required").assertExists()
    })
    capture("accounts", "Account, plan and billing", { AccountsScreen({}, {}) })
    capture("queued", "Queued changes", { QueuedChangesScreen({}) })
    capture("recovery", "Previous app · recovery", { LegacyRecoveryScreen({}) })
    val longViews = setOf("shared-home", "shared-business-new", "shared-business-edit", "shared-shop-settings", "shared-accounts", "shared-integrations")
    toList().filter { it.id in longViews }.forEach { original ->
        listOf("middle" to 1500f, "end" to 20_000f).forEach { (part, distance) ->
            add(original.copy(id = "${original.id}-$part", title = "${original.title} · $part of page", prepare = { rule ->
                original.prepare(rule)
                val matcher = SemanticsMatcher.keyIsDefined(SemanticsProperties.VerticalScrollAxisRange)
                val nodes = rule.onAllNodes(matcher).fetchSemanticsNodes()
                val index = nodes.indices.maxByOrNull { nodes[it].boundsInRoot.width * nodes[it].boundsInRoot.height }
                    ?: error("No vertical scroll area for ${original.id}")
                rule.onAllNodes(matcher)[index].performSemanticsAction(SemanticsActions.ScrollBy) { it(0f, distance) }
            }))
        }
    }
}
