package au.mainspring.nativeapp

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.DeviceRegisterBody
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/** Firebase Cloud Messaging glue for the native app. Everything is a no-op when google-services.json was not part of the build. */
object PushRegistration {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val store = object : DeviceTokenStore {
        override fun get() = TokenStore.deviceToken()
        override fun save(token: String?) = TokenStore.saveDeviceToken(token)
    }
    private val registrar = DeviceRegistrar(object : DeviceRegistryApi {
        override suspend fun register(token: String) { ApiClient.api.registerDevice(DeviceRegisterBody(token)) }
    }, store)

    fun firebaseReady(context: Context): Boolean = try { com.google.firebase.FirebaseApp.getApps(context).isNotEmpty() } catch(_: Throwable) { false }

    /** Android 13 and later need a yes from the person to show notifications; older versions always allow them. */
    fun permitted(context: Context): Boolean =
        Build.VERSION.SDK_INT < 33 || ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    private suspend fun currentToken(): String? = suspendCancellableCoroutine { cont ->
        try {
            com.google.firebase.messaging.FirebaseMessaging.getInstance().token.addOnCompleteListener { task -> cont.resume(if(task.isSuccessful) task.result else null) }
        } catch(_: Throwable) { cont.resume(null) }
    }

    /** Registers (or re-registers) this phone for the signed-in shop. Safe to call often; the server treats it as idempotent. */
    fun syncInBackground(context: Context) {
        val app = context.applicationContext
        TokenStore.init(app)
        if(!firebaseReady(app)) return
        scope.launch { registrar.sync(currentToken(), signedIn = TokenStore.getAccessToken() != null, permitted = permitted(app)) }
    }

    /** Called by Firebase when the token changes (reinstall, restore, rotation). */
    fun onNewToken(context: Context, token: String) {
        val app = context.applicationContext
        // Firebase can start the app process in the background without opening the app, so the session store may not be set up yet.
        TokenStore.init(app)
        scope.launch { registrar.sync(token, signedIn = TokenStore.getAccessToken() != null, permitted = permitted(app)) }
    }
}
