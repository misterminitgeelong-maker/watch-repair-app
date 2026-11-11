package au.mainspring.nativeapp.ui

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import au.mainspring.nativeapp.*
import com.google.android.play.core.appupdate.AppUpdateManagerFactory
import com.google.android.play.core.appupdate.AppUpdateOptions
import com.google.android.play.core.install.model.AppUpdateType
import com.google.android.play.core.install.model.InstallStatus
import com.google.android.play.core.install.model.UpdateAvailability

private fun Context.activity(): Activity? = when(this) { is Activity -> this; is ContextWrapper -> baseContext.activity(); else -> null }

/** Play checks plus a server-controlled minimum; the policy is cached for offline launches. */
@Composable fun NativeUpdateEffect(config: AndroidClientConfig, refreshPolicy: () -> Unit) {
    if(BuildConfig.DEBUG) return
    val context = LocalContext.current
    val activity = context.activity() ?: return
    val lifecycleOwner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    val manager = remember(context) { AppUpdateManagerFactory.create(context) }
    var playAvailable by remember { mutableStateOf(false) }
    var critical by remember { mutableStateOf(false) }
    var dismissed by remember { mutableStateOf(false) }
    var downloaded by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    val required = requiresNativeUpdate(config.minimum, BuildConfig.VERSION_CODE) || critical
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        if(result.resultCode != Activity.RESULT_OK) message = "The update was not installed. You can try again in Google Play."
    }
    fun store() {
        try { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=au.mainspring.app"))) }
        catch(_: android.content.ActivityNotFoundException) { message = "Open Google Play and update Mainspring." }
    }
    fun check() {
        refreshPolicy()
        manager.appUpdateInfo.addOnSuccessListener { info ->
            playAvailable = info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE
            critical = playAvailable && info.updatePriority() >= 4
            downloaded = info.installStatus() == InstallStatus.DOWNLOADED
            if(info.updateAvailability() == UpdateAvailability.DEVELOPER_TRIGGERED_UPDATE_IN_PROGRESS) {
                try { manager.startUpdateFlowForResult(info, launcher, AppUpdateOptions.newBuilder(AppUpdateType.IMMEDIATE).build()) }
                catch(_: Exception) { message = "Continue this update in Google Play." }
            }
        }.addOnFailureListener { /* Sideloaded and offline builds may have no Play listing. Server policy still works. */ }
    }
    DisposableEffect(lifecycleOwner, manager) {
        val observer = LifecycleEventObserver { _, event -> if(event == Lifecycle.Event.ON_RESUME) check() }
        val listener = com.google.android.play.core.install.InstallStateUpdatedListener { state -> downloaded = state.installStatus() == InstallStatus.DOWNLOADED }
        lifecycleOwner.lifecycle.addObserver(observer); manager.registerListener(listener); check()
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer); manager.unregisterListener(listener) }
    }
    if(required || (!dismissed && (playAvailable || downloaded))) AlertDialog(
        onDismissRequest = { if(!required) dismissed = true },
        title = { Text(if(required) "Update Mainspring to continue" else if(downloaded) "Update ready to install" else "Mainspring update available") },
        text = { Text(message ?: config.message?.takeIf { it.isNotBlank() } ?: "Install the latest version for current shop workflows.") },
        confirmButton = { TextButton({
            if(downloaded) manager.completeUpdate()
            else manager.appUpdateInfo.addOnSuccessListener { info ->
                val type = if(required) AppUpdateType.IMMEDIATE else AppUpdateType.FLEXIBLE
                if(info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE && info.isUpdateTypeAllowed(type)) {
                    try { manager.startUpdateFlowForResult(info, launcher, AppUpdateOptions.newBuilder(type).build()) }
                    catch(_: Exception) { store() }
                } else store()
            }.addOnFailureListener { store() }
        }) { Text(if(downloaded) "Restart and install" else "Update") } },
        dismissButton = { TextButton({ if(required) activity.finish() else dismissed = true }) { Text(if(required) "Close app" else "Later") } },
    )
}
