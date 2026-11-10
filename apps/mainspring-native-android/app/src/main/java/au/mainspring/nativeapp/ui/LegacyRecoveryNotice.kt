package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume

/** Checks the previous local app once; account data is only displayed in the scoped recovery screen. */
@Composable fun LegacyRecoveryNotice(onOpen: () -> Unit) {
    if(BuildConfig.DEBUG) return
    val context = LocalContext.current.applicationContext
    var visible by remember { mutableStateOf(false) }
    var checkFailed by remember { mutableStateOf(false) }
    var dismissed by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        val generation = TokenStore.sessionGeneration()
        val tenant = TokenStore.currentTenantId(); val user = TokenStore.currentUserId()
        try {
            if(!LegacyRecoveryStore.scanned(context)) {
                suspendCancellableCoroutine<Result<Unit>> { cont -> scanLegacyWork(context) { if(cont.isActive) cont.resume(it) } }.getOrThrow()
            }
            val found = withContext(Dispatchers.IO) {
                LegacyRecoveryStore.snapshot(context)?.let { snapshot ->
                    legacyDrafts(snapshot, tenant, user).isNotEmpty() || (snapshot.legacyObjects("queue") + snapshot.legacyObjects("dead")).any { it.legacyString("userId") == user }
                } ?: false
            }
            if(generation == TokenStore.sessionGeneration()) visible = found
        } catch(e: kotlinx.coroutines.CancellationException) { throw e }
        catch(_: Exception) { if(generation == TokenStore.sessionGeneration()) checkFailed = true }
    }
    if(!dismissed && (visible || checkFailed)) Surface(color = MaterialTheme.colorScheme.secondaryContainer) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
            Text(if(checkFailed) "Check saved work from the previous app." else "Previous app work is preserved on this phone.", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
            TextButton(onOpen) { Text("Review") }
            TextButton({ dismissed = true }) { Text("Later") }
        }
    }
}
