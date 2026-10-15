package au.mainspring.nativeapp.niimbot

import android.content.Context
import android.content.Intent
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.ui.LocalCalibre
import au.mainspring.nativeapp.ui.MonoLabel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/** What the print dialog is showing. Pure, so the messages are unit-testable. */
sealed class NiimbotUiState {
    object Checking : NiimbotUiState()
    data class Unavailable(val availability: NiimbotAvailability) : NiimbotUiState()
    data class Choose(val devices: List<NiimbotDevice>, val scanning: Boolean, val note: String? = null) : NiimbotUiState()
    data class Working(val message: String) : NiimbotUiState()
    object Done : NiimbotUiState()
    data class Failed(val message: String) : NiimbotUiState()
}

fun niimbotUnavailableMessage(a: NiimbotAvailability): String = when (a) {
    NiimbotAvailability.NO_BLUETOOTH_HARDWARE -> "This device has no Bluetooth LE, so it can't print to a Niimbot label printer. Use \"Print intake ticket\" instead."
    NiimbotAvailability.BLUETOOTH_OFF -> "Bluetooth is turned off. Turn it on, then try again."
    NiimbotAvailability.PERMISSION_NEEDED -> "Bluetooth permission was denied. Allow \"Nearby devices\" for this app in Settings to print labels."
    NiimbotAvailability.READY -> ""
}

/**
 * "Print label (Niimbot)" flow: permissions, scan, pick a printer, connect, print one label. Mount it when the
 * user taps the menu action and call [onDismiss] to remove it. Everything degrades to a message dialog if
 * Bluetooth is missing, off or denied. BLE I/O has not been verified on hardware.
 */
@Composable
fun NiimbotPrintDialog(label: NiimbotLabelData, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var ui by remember { mutableStateOf<NiimbotUiState>(NiimbotUiState.Checking) }
    var scanJob by remember { mutableStateOf<Job?>(null) }
    var printJob by remember { mutableStateOf<Job?>(null) }

    fun startScan() {
        scanJob?.cancel()
        val known = LinkedHashMap<String, NiimbotDevice>()
        niimbotBondedDevices(context).forEach { known[it.address] = it }
        ui = NiimbotUiState.Choose(known.values.toList(), scanning = true)
        scanJob = scope.launch {
            var failure: String? = null
            withTimeoutOrNull(12_000) {
                niimbotScan(context).catch { failure = it.message ?: "Scan failed" }.collect { d ->
                    known[d.address] = d
                    ui = NiimbotUiState.Choose(known.values.toList(), scanning = true)
                }
            }
            ui = NiimbotUiState.Choose(known.values.toList(), scanning = false, note = failure ?: if (known.isEmpty()) "No Niimbot printer found. Switch it on and keep it close." else null)
        }
    }

    fun begin() {
        val a = niimbotAvailability(context)
        if (a == NiimbotAvailability.READY) startScan() else ui = NiimbotUiState.Unavailable(a)
    }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { begin() }
    LaunchedEffect(Unit) {
        val missing = niimbotMissingPermissions(context)
        val hasHardware = niimbotAvailability(context) != NiimbotAvailability.NO_BLUETOOTH_HARDWARE
        if (hasHardware && missing.isNotEmpty()) permissionLauncher.launch(missing.toTypedArray()) else begin()
    }
    DisposableEffect(Unit) { onDispose { scanJob?.cancel(); printJob?.cancel() } }

    fun print(device: NiimbotDevice) {
        scanJob?.cancel()
        printJob = scope.launch {
            var transport: NiimbotBleTransport? = null
            var session: NiimbotSession? = null
            try {
                ui = NiimbotUiState.Working("Connecting to ${device.name}…")
                transport = NiimbotBleTransport.connect(context, device.address)
                session = NiimbotSession(transport)
                val dots = session.handshake() ?: NiimbotProtocol.DEFAULT_LABEL
                ui = NiimbotUiState.Working("Printing label…")
                val page = withContext(Dispatchers.Default) { NiimbotLabelRenderer.toRaster(label, dots) }
                session.print(listOf(page))
                ui = NiimbotUiState.Done
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                ui = NiimbotUiState.Failed(e.message?.takeIf { it.isNotBlank() } ?: "Could not print the label.")
            } finally {
                session?.close()
                transport?.close()
            }
        }
    }

    val busy = ui is NiimbotUiState.Working
    AlertDialog(
        onDismissRequest = { if (!busy) onDismiss() },
        title = { Text("Print label (Niimbot)") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (LocalCalibre.current) MonoLabel("Label / ${label.jobNumber}")
                when (val s = ui) {
                    NiimbotUiState.Checking -> Text("Checking Bluetooth…", style = MaterialTheme.typography.bodyMedium)
                    is NiimbotUiState.Unavailable -> Text(niimbotUnavailableMessage(s.availability), style = MaterialTheme.typography.bodyMedium)
                    is NiimbotUiState.Choose -> {
                        Text("Choose your printer.", style = MaterialTheme.typography.bodyMedium)
                        if (s.scanning) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            CircularProgressIndicator(Modifier.padding(4.dp), strokeWidth = 2.dp); Text("Scanning…", style = MaterialTheme.typography.bodySmall)
                        }
                        s.devices.forEach { d ->
                            TextButton(onClick = { print(d) }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("${d.name}  ·  ${d.address}") }
                        }
                        s.note?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                    is NiimbotUiState.Working -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        CircularProgressIndicator(strokeWidth = 2.dp); Text(s.message, style = MaterialTheme.typography.bodyMedium)
                    }
                    NiimbotUiState.Done -> Text("Label sent to the printer.", style = MaterialTheme.typography.bodyMedium)
                    is NiimbotUiState.Failed -> Text(s.message, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
                }
            }
        },
        confirmButton = {
            when (val s = ui) {
                is NiimbotUiState.Unavailable -> if (s.availability == NiimbotAvailability.PERMISSION_NEEDED)
                    TextButton(onClick = { openAppSettings(context) }) { Text("Open settings") }
                    else TextButton(onClick = { begin() }) { Text("Try again") }
                is NiimbotUiState.Choose -> if (!s.scanning) TextButton(onClick = { startScan() }) { Text("Scan again") }
                is NiimbotUiState.Failed -> TextButton(onClick = { begin() }) { Text("Try again") }
                else -> {}
            }
        },
        dismissButton = { if (!busy) TextButton(onClick = onDismiss, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (ui is NiimbotUiState.Done) "Close" else "Cancel") } },
    )
}

private fun openAppSettings(context: Context) {
    try {
        context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, android.net.Uri.parse("package:${context.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: Exception) {}
}
