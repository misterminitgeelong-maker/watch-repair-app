package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.SearchViewModel
import au.mainspring.nativeapp.api.SearchHit
import au.mainspring.nativeapp.searchRoute
import au.mainspring.nativeapp.ui.*

/** Global search over jobs, customers and invoices (GET /v1/search). */
@Composable
fun SearchScreen(onBack: () -> Unit, onOpenRoute: (String) -> Unit, viewModel: SearchViewModel = viewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val focus = remember { FocusRequester() }
    val recent by au.mainspring.nativeapp.RecentSearches.hits.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { try { focus.requestFocus() } catch (_: Exception) { } }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp)) {
        item { BackLargeHeader("Back", "Find", "Search", onBack) }
        item {
            AtelierTextField(
                value = state.query, onValueChange = viewModel::setQuery, singleLine = true,
                placeholder = { Text("Jobs, customers, invoices") },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp).focusRequester(focus),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            )
        }
        if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp)) }
        state.error?.let { item { ErrorBanner(it, Modifier.padding(20.dp), onRetry = { viewModel.setQuery(state.query) }) } }
        if (state.query.trim().length < SearchViewModel.MIN_CHARS) {
            item { MonoLabel("Type at least ${SearchViewModel.MIN_CHARS} characters", Modifier.padding(20.dp)) }
        } else if (state.searched && state.hits.isEmpty()) {
            item { EmptyState("No results", "Nothing matched \"${state.query.trim()}\".") }
        }
        if (state.query.trim().length < SearchViewModel.MIN_CHARS && recent.isNotEmpty()) {
            item(key = "h-recent") { SectionLabel("Recent", Modifier.padding(horizontal = 20.dp)) }
            items(recent, key = { "recent-${it.kind}-${it.id}" }) { hit -> HitRow(hit, onOpenRoute) }
        }
        section("Jobs", state.jobs, onOpenRoute)
        section("Customers", state.customers, onOpenRoute)
        section("Invoices", state.invoices, onOpenRoute)
    }
}

private fun kindLabel(kind: String) = when (kind) {
    "repair_job" -> "Watch"; "shoe_repair_job" -> "Shoe"; "auto_key_job" -> "Mobile"
    "customer" -> "Customer"; "invoice" -> "Invoice"; else -> kind
}

private fun LazyListScope.section(title: String, hits: List<SearchHit>, onOpenRoute: (String) -> Unit) {
    if (hits.isEmpty()) return
    item(key = "h-$title") { SectionLabel(title, Modifier.padding(horizontal = 20.dp)) }
    items(hits, key = { "${it.kind}-${it.id}" }) { hit -> HitRow(hit, onOpenRoute) }
}

@Composable private fun HitRow(hit: SearchHit, onOpenRoute: (String) -> Unit) {
        Column(
            Modifier.fillMaxWidth().clickable(role = androidx.compose.ui.semantics.Role.Button) { searchRoute(hit)?.let { au.mainspring.nativeapp.RecentSearches.push(hit); onOpenRoute(it) } }.heightIn(min = 56.dp).padding(horizontal = 20.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(hit.title.orEmpty().ifBlank { kindLabel(hit.kind) }, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium, maxLines = 1)
                Text("›", style = MaterialTheme.typography.titleLarge)
            }
            MonoLabel(listOfNotNull(kindLabel(hit.kind), hit.subtitle?.takeIf { it.isNotBlank() }, hit.status?.takeIf { it.isNotBlank() && it != hit.subtitle }?.let(::statusLabel)).joinToString(" · "))
        }
        HorizontalDivider(Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.outlineVariant)
}
