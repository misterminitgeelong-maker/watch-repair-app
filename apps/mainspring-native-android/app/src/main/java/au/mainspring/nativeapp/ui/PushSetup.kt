package au.mainspring.nativeapp.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.PushRegistration
import au.mainspring.nativeapp.PushRouteInbox
import au.mainspring.nativeapp.ui.screens.findFragmentActivity
import kotlinx.coroutines.delay

private const val PREFS = "mainspring_push_prefs"
private const val K_ASKED = "asked_for_permission"

private fun asked(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(K_ASKED, false)
private fun markAsked(context: Context) { context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(K_ASKED, true).apply() }

/**
 * Runs inside the signed-in app: registers this phone for push, asks once (Android 13 and later) for permission to show alerts
 * a moment after sign-in, and opens the screen a tapped notification points at. Does nothing when the build has no Firebase file.
 */
@Composable fun PushSetupEffect(open: (String) -> Unit) {
    val context = LocalContext.current
    val pending by PushRouteInbox.pending.collectAsState()
    LaunchedEffect(pending) { pending?.let { route -> open(route); PushRouteInbox.consume(route) } }
    if(!PushRegistration.firebaseReady(context)) return
    var ask by remember { mutableStateOf(false) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> if(granted) PushRegistration.syncInBackground(context) }
    LaunchedEffect(Unit) {
        if(PushRegistration.permitted(context)) PushRegistration.syncInBackground(context)
        // Only in the real app, never in screens hosted by tests.
        else if(!asked(context) && context.findFragmentActivity() is au.mainspring.nativeapp.MainActivity) { delay(2500); ask = true }
    }
    if(ask) AlertDialog(onDismissRequest = { ask = false; markAsked(context) }, title = { Text("Get shop alerts?") },
        text = { Text("Mainspring can tell you when a customer approves or declines a quote, an invoice is paid, a customer replies, or a new lead arrives.") },
        confirmButton = { TextButton({ ask = false; markAsked(context); if(Build.VERSION.SDK_INT >= 33) launcher.launch(Manifest.permission.POST_NOTIFICATIONS) }, Modifier.testTag("push-allow")) { Text("Turn on") } },
        dismissButton = { TextButton({ ask = false; markAsked(context) }, Modifier.testTag("push-later")) { Text("Not now") } })
}

/** Settings row: shows whether alerts are on and lets the person turn them on later (after saying Not now). Hidden when push is not set up in this build. */
@Composable fun PushSettingRow() {
    val context = LocalContext.current
    if(!PushRegistration.firebaseReady(context)) return
    var on by remember { mutableStateOf(PushRegistration.permitted(context)) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted -> on = granted; if(granted) PushRegistration.syncInBackground(context) }
    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("push-setting"), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Column(Modifier.weight(1f)) {
            Text("Shop alerts on this phone", style = MaterialTheme.typography.bodyLarge)
            Text(if(on) "On: quote replies, paid invoices, customer replies and new leads." else "Off. Turn on to hear about quote replies, paid invoices and customer messages.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if(!on) TextButton({
            if(Build.VERSION.SDK_INT >= 33) launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
            else context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
        }) { Text("Turn on") }
    }
}
