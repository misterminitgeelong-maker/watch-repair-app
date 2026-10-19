package au.mainspring.nativeapp.ui.screens

import android.content.Context
import android.content.ContextWrapper
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
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
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import au.mainspring.nativeapp.AppLock

internal fun Context.findFragmentActivity(): FragmentActivity? {
    var c: Context? = this
    while(c is ContextWrapper) { if(c is FragmentActivity) return c; c = c.baseContext }
    return null
}

/** Covers the app until the phone confirms the person (fingerprint, face or phone PIN). Never asks for the shop password. */
@Composable fun AppLockOverlay(onUnlock: () -> Unit, onSignOut: () -> Unit) {
    val activity = LocalContext.current.findFragmentActivity()
    var message by remember { mutableStateOf<String?>(null) }
    val ask = { activity?.let { AppLock.prompt(it, "Unlock Mainspring", onUnlock, { err -> message = err }) } ?: Unit }
    LaunchedEffect(Unit) { ask() }
    Surface(Modifier.fillMaxSize().testTag("app-lock").pointerInput(Unit) { detectTapGestures { } }, color = MaterialTheme.colorScheme.background) {
        Column(Modifier.systemBarsPadding().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
            androidx.compose.foundation.Image(androidx.compose.ui.res.painterResource(au.mainspring.nativeapp.R.drawable.ic_launcher_vector), contentDescription = null, modifier = Modifier.size(88.dp))
            Spacer(Modifier.size(16.dp))
            Text("Mainspring is locked", Modifier.semantics { heading() }, style = MaterialTheme.typography.headlineSmall)
            Text("Use your fingerprint, face or phone PIN to continue.", Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            message?.let { Text(it, Modifier.padding(top = 8.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            Button({ message = null; ask() }, Modifier.fillMaxWidth().padding(top = 24.dp).heightIn(min = 48.dp).testTag("app-lock-unlock")) { Text("Unlock") }
            TextButton(onSignOut, Modifier.padding(top = 8.dp).heightIn(min = 48.dp)) { Text("Sign out") }
        }
    }
}
