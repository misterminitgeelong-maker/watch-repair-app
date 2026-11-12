package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.ui.*

/** A dedicated shopfront home: request a mobile visit and follow its response without repair-only tools. */
@Composable fun BookingOnlyHomeScreen(onNavigate: (String) -> Unit, shopName: String? = null, vm: BookingViewModel = viewModel(key = "booking-only-home")) {
    val s by vm.state.collectAsStateWithLifecycle()
    val messages by NetworkUnreadStore.count.collectAsStateWithLifecycle()
    val alerts by InboxCountStore.count.collectAsStateWithLifecycle()
    val lifecycleOwner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner) { lifecycleOwner.lifecycle.repeatOnLifecycle(androidx.lifecycle.Lifecycle.State.STARTED) { while(true) { kotlinx.coroutines.delay(30_000); vm.refresh() } } }
    LazyColumn(Modifier.fillMaxSize().testTag("booking-only-home"), contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 16.dp, bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item {
            PageTitle(shopName?.takeIf(String::isNotBlank) ?: "Your shop")
            Text("Book a mobile locksmith", style = MaterialTheme.typography.headlineSmall)
            Text("Send your customer’s details to your network operator, then follow the booking here.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(12.dp))
            Button({ onNavigate("newBookingRequest") }, modifier = Modifier.fillMaxWidth().heightIn(min = 44.dp).testTag("booking-home-new")) { Text("New booking request") }
        }
        if(s.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
        s.error?.let { item { ErrorBanner(it, onRetry = vm::refresh) } }
        item {
            FlatPanel {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) { Text("Booking requests", style = MaterialTheme.typography.titleLarge); TextButton({ onNavigate("bookingRequests") }) { Text("View all") } }
                Text("${s.total} requests")
                if(s.rows.isNotEmpty()) {
                    Text("In the ${s.rows.size} loaded requests: ${s.rows.count { it.status == "pending" }} awaiting a response · ${s.rows.count { it.status == "accepted" }} accepted · ${s.rows.count { it.status == "moved_to_pool" }} in dispatch pool", style = MaterialTheme.typography.bodySmall)
                } else if(!s.loading && s.error == null) Text("Your first request will appear here.")
            }
        }
        items(s.rows.take(5), key = { "recent-${it.id}" }) { row ->
            FlatPanel {
                Text(row.customer, style = MaterialTheme.typography.titleMedium)
                Text(bookingStatusLabel(row.status), color = MaterialTheme.colorScheme.primary)
                Text("${row.operator} · ${row.address}")
                if(row.offerCount > 1) Text("Re-offered · offer ${row.offerCount}", style = MaterialTheme.typography.bodySmall)
                row.offerExpiresAt?.takeIf { row.status == "pending" }?.let { Text("Response due ${formatShopDate(it)}", style = MaterialTheme.typography.bodySmall) }
            }
        }
        item { SectionLabel("YOUR NETWORK") }
        item {
            bookingOnlyDestinations(TokenStore.isOwner()).filter { it.first != "bookingRequests" }.forEach { (route, label) ->
                val count = when(route) { "networkMessages" -> messages; "inbox" -> alerts; else -> 0 }
                OutlinedButton({ onNavigate(route) }, modifier = Modifier.fillMaxWidth().heightIn(min = 44.dp).testTag("booking-home-$route")) { Text(label + if(count > 0) " ($count)" else "") }
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}
