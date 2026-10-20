package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.niimbot.NiimbotPrintDialog
import kotlinx.coroutines.CancellationException

/** What the post-intake prompt is doing. Pure so the wording is unit-testable. */
enum class PrintAfterIntakeMode { ASK, LOADING_LABELS, LOADING_TICKETS, LABELS, ERROR }

fun printAfterIntakeTitle(jobCount: Int): String = if (jobCount > 1) "Print labels for $jobCount jobs?" else "Print labels?"

fun printAfterIntakeBody(jobCount: Int, kind: IntakeTicketKind): String {
    val per = "a workshop copy and a customer copy"
    return if (jobCount > 1) "$jobCount ${kind.label.lowercase()} jobs were created. Print $per for each on the Niimbot label printer, or print the A4 tickets."
    else "The ${kind.label.lowercase()} job was created. Print $per on the Niimbot label printer, or print the A4 ticket."
}

/**
 * Offered right after an intake completes, like the web "Print job ticket now?" step. [Print] runs the Niimbot flow
 * (auto-connecting to the last printer) for the workshop and customer copy of every created job; the A4 option
 * uses Android PrintManager. [onDone] is called on "Not now" and after printing is finished or abandoned.
 */
@Composable
fun PrintAfterIntakeDialog(kind: IntakeTicketKind, jobIds: List<String>, apiBaseUrl: String, onDone: () -> Unit) {
    val context = LocalContext.current
    var mode by remember { mutableStateOf(PrintAfterIntakeMode.ASK) }
    var bundles by remember { mutableStateOf<List<JobPrintBundle>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var request by remember { mutableStateOf<PrintAfterIntakeMode?>(null) }

    LaunchedEffect(request) {
        val wanted = request ?: return@LaunchedEffect
        mode = wanted
        try {
            bundles = loadJobBundles(kind, jobIds, apiBaseUrl)
            if (bundles.isEmpty()) throw IllegalStateException("Nothing to print yet. Open the job and print from its menu.")
            if (wanted == PrintAfterIntakeMode.LOADING_TICKETS) {
                printIntakeTickets(context, bundles.map { it.ticket })
                onDone()
            } else mode = PrintAfterIntakeMode.LABELS
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            error = e.message?.takeIf { it.isNotBlank() } ?: "Could not prepare the print."
            mode = PrintAfterIntakeMode.ERROR
        }
        request = null
    }

    if (mode == PrintAfterIntakeMode.LABELS) {
        NiimbotPrintDialog(bundles.flatMap { it.labels }, onDone)
        return
    }
    val busy = mode == PrintAfterIntakeMode.LOADING_LABELS || mode == PrintAfterIntakeMode.LOADING_TICKETS
    AlertDialog(
        onDismissRequest = { if (!busy) onDone() },
        title = { Text(printAfterIntakeTitle(jobIds.size)) },
        text = {
            when {
                busy -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    CircularProgressIndicator(strokeWidth = 2.dp); Text("Preparing…", style = MaterialTheme.typography.bodyMedium)
                }
                mode == PrintAfterIntakeMode.ERROR -> Text(error.orEmpty(), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
                else -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(printAfterIntakeBody(jobIds.size, kind), style = MaterialTheme.typography.bodyMedium)
                    TextButton(onClick = { request = PrintAfterIntakeMode.LOADING_TICKETS }, modifier = Modifier.heightIn(min = 48.dp).padding(0.dp)) { Text("Print A4 ticket instead") }
                }
            }
        },
        confirmButton = {
            if (mode == PrintAfterIntakeMode.ASK) TextButton(onClick = { request = PrintAfterIntakeMode.LOADING_LABELS }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Print") }
            else if (mode == PrintAfterIntakeMode.ERROR) TextButton(onClick = { mode = PrintAfterIntakeMode.ASK }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Try again") }
        },
        dismissButton = { if (!busy) TextButton(onClick = onDone, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (mode == PrintAfterIntakeMode.ERROR) "Close" else "Not now") } },
    )
}

private suspend fun loadJobBundles(kind: IntakeTicketKind, jobIds: List<String>, apiBaseUrl: String): List<JobPrintBundle> {
    val api = ApiClient.api
    val ctx = JobPrintContext(apiBaseUrl, TokenStore.shopValue("name"), TokenStore.shopValue("phone"),
        { formatCents(it, TokenStore.shopValue("currency") ?: "AUD") }, { formatShopDate(it) })
    return jobIds.mapNotNull { id ->
        when (kind) {
            IntakeTicketKind.WATCH -> watchJobBundle(api.getRepairJob(id), ctx)
            IntakeTicketKind.SHOE -> {
                val job = api.getShoeRepairJob(id)
                val customer = job.shoe?.customerId?.let { try { api.getCustomer(it) } catch (e: CancellationException) { throw e } catch (_: Exception) { null } }
                shoeJobBundle(job, customer?.fullName, customer?.phone, ctx)
            }
        }
    }
}
