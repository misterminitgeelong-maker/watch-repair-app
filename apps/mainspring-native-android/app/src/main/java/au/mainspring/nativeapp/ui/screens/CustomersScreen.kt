package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import au.mainspring.nativeapp.alphaSections
import au.mainspring.nativeapp.countLabel
import au.mainspring.nativeapp.CUSTOMER_SORTS
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.CustomersViewModel
import au.mainspring.nativeapp.api.CustomerRead
import au.mainspring.nativeapp.ui.*

/** Sticky section header (letter / day) with an opaque background so rows scroll cleanly beneath it. */
@Composable internal fun SectionHeader(text: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background).padding(horizontal = 24.dp, vertical = 6.dp).semantics { heading() }) {
        if(LocalCalibre.current) MonoLabel(text) else Text(text.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** People tab: customers as Atelier cards under a large "People" header with a round + button. */
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
fun CustomersScreen(
    onOpenCustomer: (String) -> Unit,
    onNewCustomer: () -> Unit,
    viewModel: CustomersViewModel = viewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    RefreshOnResume(viewModel::refresh)
    val calibre = LocalCalibre.current
    au.mainspring.nativeapp.ui.PullRefresh(state.loading, viewModel::refresh, Modifier.fillMaxSize()) { LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(if(calibre) 0.dp else 8.dp)) {
        if(calibre) item { CalibreCustomersTop(state.query, state.sort, viewModel::setQuery, viewModel::setSort, viewModel::refresh, onNewCustomer, state.customers) }
        else {
            item { LargeHeader("Directory · Accounts", "Customers", onAdd = onNewCustomer, addDescription = "New customer") }
            item {
                au.mainspring.nativeapp.ui.AtelierTextField(
                    value = state.query, onValueChange = viewModel::setQuery, singleLine = true,
                    placeholder = { Text("Search customers") }, shape = MaterialTheme.shapes.small,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp),
                    colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.surface, focusedContainerColor = MaterialTheme.colorScheme.surface,
                        unfocusedBorderColor = androidx.compose.ui.graphics.Color.Transparent, focusedBorderColor = MaterialTheme.colorScheme.primary),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { viewModel.refresh() }),
                )
            }
            item {
                Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    CUSTOMER_SORTS.forEach { (key, label) -> TabChip(state.sort == key, { viewModel.setSort(key) }, { Text(label) }, Modifier.testTag("customer-sort-$key")) }
                }
            }
        }
        if (state.loading && state.customers.isEmpty()) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        state.error?.let { item { ErrorBanner(it, Modifier.padding(horizontal = 20.dp), onRetry = { viewModel.refresh() }) } }
        if (!state.loading && state.error == null && state.customers.isEmpty()) item { EmptyState("No customers found", "Try a different name, or add a new customer with the + button.", icon = "customers") }
        if (state.customers.isNotEmpty() && !calibre) item(key = "count") {
            Text(countLabel(state.customers.size, "customer", more = state.canLoadMore), Modifier.padding(horizontal = 24.dp).testTag("customers-count"), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        val byName = state.sort.startsWith("name") && !calibre
        val sections = if (byName) alphaSections(state.customers) { it.fullName } else listOf("" to state.customers)
        sections.forEach { (letter, rows) ->
            if (letter.isNotEmpty()) stickyHeader(key = "letter-$letter-${rows.first().id}", contentType = "letter") { SectionHeader(letter) }
            items(rows, key = { it.id }) { c ->
                if(calibre) CalibreCustomerRow(c, { onOpenCustomer(c.id) }, first = c.id == rows.first().id, last = c.id == rows.last().id && !state.canLoadMore, modifier = Modifier.padding(horizontal = 20.dp))
                else ListCard({ onOpenCustomer(c.id) }, Modifier.padding(horizontal = 20.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(c.fullName, style = MaterialTheme.typography.titleMedium, maxLines = 1)
                            listOfNotNull(c.phone, c.email, au.mainspring.nativeapp.customerAddedLabel(c.createdAt, au.mainspring.nativeapp.TokenStore.calendarTimezone()).ifBlank { null }).filter { it.isNotBlank() }.takeIf { it.isNotEmpty() }?.let {
                                Text(it.joinToString(" · "), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1)
                            }
                        }
                        Text("›", style = MaterialTheme.typography.titleLarge)
                    }
                }
            }
        }
        if (state.canLoadMore) item {
            SecondaryAction(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp)) { Text("Load more customers") }
        }
    } }
}

/** One bordered white card per customer, as on the web: name in the accent colour, email, phone, added date. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable private fun CalibreCustomerRow(c: CustomerRead, onClick: () -> Unit, first: Boolean, last: Boolean, modifier: Modifier = Modifier) {
    val light = MaterialTheme.colorScheme.outlineVariant
    val dark = MaterialTheme.colorScheme.onSurface
    Surface(onClick, modifier.fillMaxWidth().drawBehind {
        val w = 1.dp.toPx()
        drawLine(light, androidx.compose.ui.geometry.Offset(w / 2, 0f), androidx.compose.ui.geometry.Offset(w / 2, size.height), w)
        drawLine(light, androidx.compose.ui.geometry.Offset(size.width - w / 2, 0f), androidx.compose.ui.geometry.Offset(size.width - w / 2, size.height), w)
        if(first) drawLine(light, androidx.compose.ui.geometry.Offset(0f, w / 2), androidx.compose.ui.geometry.Offset(size.width, w / 2), w)
        drawLine(if(last) light else dark, androidx.compose.ui.geometry.Offset(0f, size.height - w / 2), androidx.compose.ui.geometry.Offset(size.width, size.height - w / 2), w)
    }, color = MaterialTheme.colorScheme.surface, shape = androidx.compose.ui.graphics.RectangleShape) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(c.fullName, style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.primary, maxLines = 1)
            Spacer(Modifier.height(6.dp))
            Text(c.email?.takeIf { it.isNotBlank() } ?: "No email", style = MaterialTheme.typography.bodyMedium, maxLines = 1)
            Text(c.phone?.takeIf { it.isNotBlank() } ?: "No phone", style = MaterialTheme.typography.bodyMedium, maxLines = 1)
            au.mainspring.nativeapp.customerAddedLabel(c.createdAt, au.mainspring.nativeapp.TokenStore.calendarTimezone()).ifBlank { null }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

/** Web-style customers header: title and Add Customer, then search and a sort select in one row. */
@Composable private fun CalibreCustomersTop(query: String, sort: String, onQuery: (String) -> Unit, onSort: (String) -> Unit, onSearch: () -> Unit, onNewCustomer: () -> Unit, customers: List<CustomerRead>) {
    var open by remember { mutableStateOf(false) }
    var mergeInfo by remember { mutableStateOf(false) }
    Column(Modifier.padding(bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        PageTitle("Customers", Modifier.padding(start = 0.dp))
        Row(Modifier.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SecondaryAction({ mergeInfo = true }, Modifier.heightIn(min = 48.dp).testTag("merge-duplicates"), shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp)) { Text("Merge duplicates") }
            PrimaryAction(onNewCustomer, Modifier.semantics { contentDescription = "New customer" }, shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp)) { Text("+  Add Customer") }
        }
        Row(Modifier.padding(horizontal = 20.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            AtelierTextField(
                value = query, onValueChange = onQuery, singleLine = true, placeholder = { Text("Search customers…") },
                modifier = Modifier.weight(1f), shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
                colors = OutlinedTextFieldDefaults.colors(unfocusedContainerColor = MaterialTheme.colorScheme.surface, focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant, focusedBorderColor = MaterialTheme.colorScheme.primary),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search), keyboardActions = KeyboardActions(onSearch = { onSearch() }),
            )
            Box {
                SecondaryAction({ open = true }, Modifier.heightIn(min = 56.dp).testTag("customer-sort"), shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp)) {
                    Text((CUSTOMER_SORTS.firstOrNull { it.first == sort }?.second ?: "Sort") + " ▾", maxLines = 1)
                }
                DropdownMenu(open, { open = false }) {
                    CUSTOMER_SORTS.forEach { (key, label) -> DropdownMenuItem({ Text(label) }, { onSort(key); open = false }, Modifier.testTag("customer-sort-$key")) }
                }
            }
        }
    }
    if(mergeInfo) MergeDuplicatesSheet(customers, { mergeInfo = false }, onMerged = onSearch)
}
