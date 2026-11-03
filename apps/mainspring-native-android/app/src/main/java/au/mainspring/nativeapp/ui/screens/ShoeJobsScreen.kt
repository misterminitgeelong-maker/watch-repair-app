package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.SHOE_ACTIVE_STATUSES
import au.mainspring.nativeapp.SHOE_CLOSED_STATUSES
import au.mainspring.nativeapp.ShoeJobsViewModel
import au.mainspring.nativeapp.ShoeServicesViewModel
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.ui.JobThumb
import au.mainspring.nativeapp.ui.SecondaryAction
import au.mainspring.nativeapp.ui.formatCents
import au.mainspring.nativeapp.ui.statusLabel

private val SHOE_URGENT_STATUSES = setOf("no_go", "failed_job", "job_delayed", "declined", "overdue", "urgent")

/** The web's four shoe board stages (frontend/src/components/kanban/columns.ts): label, statuses, top-edge colour, badge tint. */
private class ShoeStage(val key: String, val label: String, val statuses: Set<String>, val color: Color, val tint: Color)
private val SHOE_STAGES = listOf(
    ShoeStage("quote", "Quote Needed", setOf("awaiting_quote", "awaiting_customer_details"), Color(0xFF9A6E26), Color(0xFFF6EDD8)),
    ShoeStage("approval", "Awaiting Approval", setOf("awaiting_go_ahead", "quote_sent"), Color(0xFF2A5FA0), Color(0xFFEDF3FA)),
    ShoeStage("in_work", "In Work", setOf("go_ahead", "awaiting_parts", "parts_to_order", "working_on", "service"), Color(0xFF6840B4), Color(0xFFF3EBF9)),
    ShoeStage("collect", "Ready to Collect", setOf("completed", "awaiting_collection", "collected"), Color(0xFF1A6A3A), Color(0xFFEBF8EF)),
)

/** Same cut-off the server uses for "cost outliers" (cost_cents > 5,000,000). */
private const val SHOE_COST_OUTLIER_CENTS = 5_000_000

/**
 * Shoe service screen, top to bottom like the web phone view: title, Queue + "+ New Job", intro line, Jobs | Services, the
 * collapsible "Pricing combos & guarantee" row, Active | Completed, Board | Cards, search, status select, "Cost outliers
 * only", age select, then the board columns or job cards and a floating "+ New Job".
 */
@Composable
fun ShoeJobsScreen(
    onBack: () -> Unit,
    onOpenJob: (String) -> Unit,
    onNewJob: () -> Unit,
    onOpenQueue: (() -> Unit)? = null,
    onLogWork: ((String) -> Unit)? = null,
    viewModel: ShoeJobsViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    au.mainspring.nativeapp.ui.RefreshOnResume(viewModel::refresh)
    var tab by rememberSaveable { mutableStateOf("jobs") }
    var combosOpen by rememberSaveable { mutableStateOf(false) }
    var costOutliers by rememberSaveable { mutableStateOf(false) }
    var minDays by rememberSaveable { mutableStateOf(0) }
    val currency = TokenStore.shopValue("currency") ?: "AUD"
    val rows = state.visible.filter { j ->
        (!costOutliers || j.costCents > SHOE_COST_OUTLIER_CENTS) && (minDays == 0 || au.mainspring.nativeapp.daysInShop(j.createdAt) >= minDays)
    }
    LaunchedEffect(rows) { au.mainspring.nativeapp.JobNavContext.set("shoe", rows.map { it.id }) }
    val allLabel = "All in " + (if (state.showCompleted) "completed" else "active")

    val header: @Composable () -> Unit = {
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ServiceTitle("Shoe Repairs", Modifier.padding(top = 8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End), verticalAlignment = Alignment.CenterVertically) {
                if (onOpenQueue != null) WebButton("Queue", onOpenQueue, icon = "list", tag = "queue-button")
                WebButton("New Job", onNewJob, primary = true, icon = "plus", tag = "new-job-ticket")
            }
            Text("Soles, heels, stitching, cleaning, and more. Multi-pair intake with combo pricing.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SandSegmented(listOf(ToggleOption("jobs", "Jobs", "tab-jobs"), ToggleOption("catalogue", "Services", "tab-catalogue")), tab, { tab = it })
            CollapsibleRow("Pricing combos & guarantee", "shield", combosOpen, { combosOpen = !combosOpen }, tag = "combos-toggle") { ShoeCombosPanel() }
            if (tab == "jobs") {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    SandSegmented(listOf(ToggleOption("active", "Active (${state.activeCount})", "segment-active"), ToggleOption("completed", "Completed (${state.completedCount})", "segment-completed")),
                        if (state.showCompleted) "completed" else "active", { viewModel.setShowCompleted(it == "completed") })
                }
                AccentToggle(listOf(ToggleOption("board", "Board", "view-board"), ToggleOption("list", "Cards", "view-list")),
                    if (state.board) "board" else "list", { viewModel.setBoard(it == "board") })
                WebSearchField(state.query, viewModel::setQuery, "Search jobs or services...")
                WebSelect(if (state.statusFilter == "all") allLabel else statusLabel(state.statusFilter),
                    listOf("all" to allLabel) + (if (state.showCompleted) SHOE_CLOSED_STATUSES else SHOE_ACTIVE_STATUSES).map { it to statusLabel(it) },
                    viewModel::setStatusFilter, tag = "status-filter", description = "Filter by status")
                if (state.savedViews.isNotEmpty()) Text("Saved views", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                au.mainspring.nativeapp.ui.SavedViewsRow(state.savedViews,
                    { viewModel.currentView().copy(minDaysInShop = minDays.takeIf { it > 0 }, costOutliers = costOutliers) },
                    { v -> viewModel.applyView(v); minDays = v.minDaysInShop ?: 0; costOutliers = v.costOutliers },
                    viewModel::saveView, viewModel::deleteView, Modifier.testTag("saved-views"), horizontalPadding = 0.dp)
                WebCheckRow("Cost outliers only", costOutliers, { costOutliers = it }, tag = "cost-outliers")
                WebSelect(if (minDays == 0) "Any age" else "$minDays+ days in shop",
                    listOf("0" to "Any age", "7" to "7+ days in shop", "14" to "14+ days in shop", "21" to "21+ days in shop"),
                    { minDays = it.toInt() }, tag = "age-filter", description = "Filter by age in shop")
                if (state.loading && state.jobs.isEmpty()) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = { viewModel.refresh() }) }
                if (!state.loading && state.error == null && state.jobs.isEmpty()) au.mainspring.nativeapp.ui.EmptyState("No shoe repairs yet", "Tap New Job to book in a pair.")
                if (!state.loading && state.error == null && state.jobs.isNotEmpty() && rows.isEmpty() && !state.board) au.mainspring.nativeapp.ui.EmptyState("No repairs match", "Try a different search or filter.")
            }
        }
    }

    Box(Modifier.fillMaxSize()) {
        if (tab == "catalogue") {
            val services: ShoeServicesViewModel = viewModel()
            val servicesState by services.state.collectAsStateWithLifecycle()
            LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                item { header() }
                shoeServicesBody(servicesState, services)
            }
        } else if (state.board) {
            au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    header()
                    val byId = rows.associateBy { it.id }
                    val cards = rows.map { BoardCard(it.id, it.title, listOfNotNull(it.jobNumber, state.customerName(it)).joinToString(" · "), it.status) }
                    val staged = SHOE_STAGES.map { st -> WebKanbanColumn(st.key, st.label, st.color, st.tint, cards.filter { it.status in st.statuses }) }
                    val orphans = cards.filter { c -> SHOE_STAGES.none { c.status in it.statuses } }
                    val columns = if (orphans.isEmpty()) staged else staged + WebKanbanColumn("other", "Other", Color(0xFF596068), Color(0xFFEEF1F4), orphans)
                    val canMove = TokenStore.canWorkJobs() && state.movingId == null
                    val targets = au.mainspring.nativeapp.SHOE_JOB_STATUS_OPTIONS.map { it to statusLabel(it) }
                    ZoomableBoard("shoe", columns.size, 168.dp) {
                        WebKanban(columns) { card, color ->
                        val job = byId[card.id]
                        ShoeBoardCard(card, job?.jobNumber ?: "", job?.let { state.customerName(it) }, color, canMove, targets, onOpenJob, viewModel::moveJob, { id, st, why -> viewModel.moveJob(id, st, why) },
                            onLogWork = if (TokenStore.canWorkJobs()) onLogWork else null)
                    }
}
                }
            }
        } else {
            au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 96.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item { header() }
                    items(rows, key = { it.id }) { j ->
                        ServiceJobCard({ onOpenJob(j.id) }, j.jobNumber, j.title, state.customerName(j), statusLabel(j.status), j.status,
                            shortDaysInShop(au.mainspring.nativeapp.daysInShop(j.createdAt)),
                            j.costCents.takeIf { it > 0 }?.let { "Quote ${formatCents(it, currency)}" },
                            thumb = { JobThumb("shoe", j.id, size = 56.dp) }, urgent = j.status in SHOE_URGENT_STATUSES,
                            modifier = Modifier.padding(horizontal = 16.dp))
                    }
                    if (state.canLoadMore) item {
                        SecondaryAction(viewModel::loadMore, Modifier.padding(horizontal = 16.dp).fillMaxWidth(), enabled = !state.loading) { Text("Load more repairs") }
                    }
                }
            }
        }
        BoardMoveToastBar(state.moveToast, viewModel::undoMove, viewModel::clearMoveToast, Modifier.align(Alignment.BottomCenter).padding(bottom = 84.dp))
        NewJobFab(onNewJob, Modifier.align(Alignment.BottomEnd).padding(end = 16.dp, bottom = 16.dp))
    }
}

/** Combo rules and the guarantee, loaded only when the "Pricing combos & guarantee" row is opened. */
@Composable
private fun ShoeCombosPanel(viewModel: ShoeServicesViewModel = viewModel()) {
    val s by viewModel.state.collectAsStateWithLifecycle()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (s.loading && s.combos.isEmpty() && s.guarantee == null) LinearProgressIndicator(Modifier.fillMaxWidth())
        s.combos.forEach { combo ->
            WebCard(padding = 14.dp) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(combo.name, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                    ((combo.discounts ?: emptyList()) + listOfNotNull(combo.discount)).filter { it.isNotBlank() }.forEach { d ->
                        Text(d, Modifier.background(MaterialTheme.colorScheme.primary, RoundedCornerShape(50)).padding(horizontal = 8.dp, vertical = 2.dp), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onPrimary)
                    }
                }
                combo.rule?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
        s.guarantee?.takeIf { it.isNotBlank() }?.let { g ->
            Row(Modifier.fillMaxWidth().background(Color(0x14829F64), RoundedCornerShape(10.dp)).border(1.dp, Color(0x40829F64), RoundedCornerShape(10.dp)).padding(14.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                au.mainspring.nativeapp.ui.GlyphIcon("shield", size = 16.dp, color = Color(0xFF6A9A50))
                Text(g, style = MaterialTheme.typography.bodyMedium)
            }
        }
        if (!s.loading && s.combos.isEmpty() && s.guarantee.isNullOrBlank()) Text("No combo pricing set up.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** One job in a board column: job number in the column colour, title, customer, and the native "Move to..." menu. */
@Composable
private fun ShoeBoardCard(card: BoardCard, number: String, customer: String?, color: Color, canMove: Boolean, moveTargets: List<Pair<String, String>>,
    onOpen: (String) -> Unit, onMove: (String, String) -> Unit, onMoveReason: (String, String, String?) -> Unit, onLogWork: ((String) -> Unit)? = null) {
    var menu by remember(card.id, card.status) { mutableStateOf(false) }
    HoldMenuTicket(card.title, card.status, moveTargets, canMove, null, { onOpen(card.id) }, { st, why -> onMoveReason(card.id, st, why) }, onLogWork = onLogWork?.let { f -> { f(card.id) } }) {
Surface(Modifier.fillMaxWidth().testTag("board-card-${card.id}"), shape = RoundedCornerShape(4.dp), color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(number, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = color, maxLines = 1)
            Text(card.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (!customer.isNullOrBlank()) Text(customer, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (canMove) {
                TextButton(onClick = { menu = true }, modifier = Modifier.heightIn(min = 48.dp).testTag("board-move-${card.id}")) { Text("Move to…") }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    moveTargets.filter { it.first != card.status }.forEach { (status, label) ->
                        DropdownMenuItem(text = { Text(label) }, onClick = { menu = false; onMove(card.id, status) }, modifier = Modifier.testTag("board-target-${card.id}-$status"))
                    }
                }
            }
        }
    }
}
}
