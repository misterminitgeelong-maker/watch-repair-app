package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.AcceptBookingLink
import au.mainspring.nativeapp.AcceptBookingViewModel
import au.mainspring.nativeapp.DeepLinkInbox
import au.mainspring.nativeapp.BookingDeepLink
import au.mainspring.nativeapp.ui.*
import androidx.compose.runtime.collectAsState

/** Opened by an accept-booking deep link. [onOpenJob] receives the job created by accepting, when the backend returns one. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun AcceptBookingScreen(bookingId: String, onBack: () -> Unit, onOpenJob: (String) -> Unit, onOpenRequests: () -> Unit = onBack,
    vm: AcceptBookingViewModel = viewModel(key = "accept-booking-$bookingId", factory = AcceptBookingViewModel.factory(bookingId))) {
    val state by vm.state.collectAsStateWithLifecycle()
    val booking = state.booking
    Scaffold(topBar = { AtelierTopAppBar(title = { Text("Booking request") }, navigationIcon = { BackButton(onClick = onBack) }) }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if(state.loading || state.accepting) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let { ErrorBanner(it) }
            if(booking != null) FlatPanel {
                DetailRow("Customer", booking.customer)
                DetailRow("From", booking.shop)
                DetailRow("Address", booking.address)
                booking.schedule?.takeIf { it.isNotBlank() }?.let { DetailRow("Preferred time", it) }
                booking.notes?.takeIf { it.isNotBlank() }?.let { DetailRow("Notes", it) }
                DetailRow("Status", statusLabel(booking.status))
                booking.conflict?.takeIf { it.isNotBlank() }?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            } else if(!state.loading) Text("Accept this booking request from a shop. It will become a mobile job in your queue.", style = MaterialTheme.typography.bodyMedium)
            val result = state.result
            if(result != null) {
                Text("Booking accepted.", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary)
                result.jobId?.let { id -> PrimaryAction({ onOpenJob(id) }) { Text("Open job") } }
                SecondaryAction(onOpenRequests) { Text("All booking requests") }
            } else {
                val alreadyHandled = booking != null && booking.status != "pending"
                PrimaryAction(vm::accept, enabled = !state.loading && !state.accepting && !alreadyHandled) { Text(if(state.accepting) "Accepting..." else "Accept and quote") }
                if(alreadyHandled) Text("This request is already ${booking?.status}.", style = MaterialTheme.typography.bodySmall)
                SecondaryAction(onOpenRequests) { Text("All booking requests") }
            }
        }
    }
}

/**
 * Hook for the signed-in shell: when [DeepLinkInbox] holds an accept-booking link, navigates to it via [navigate] and consumes it.
 * Call once inside the NavHost's parent: `AcceptBookingLinkEffect { route -> navController.navigate(route) }`.
 */
@Composable fun AcceptBookingLinkEffect(navigate: (route: String) -> Unit) {
    val pending: AcceptBookingLink? by DeepLinkInbox.pending.collectAsState()
    LaunchedEffect(pending) {
        val link = pending ?: return@LaunchedEffect
        navigate(BookingDeepLink.route(link.bookingId))
        DeepLinkInbox.consume(link)
    }
}
