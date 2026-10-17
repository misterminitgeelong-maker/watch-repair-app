package au.mainspring.nativeapp

import android.os.Bundle
import androidx.fragment.app.FragmentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ui.MainspringAppShell
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.LoginScreen
import au.mainspring.nativeapp.ui.screens.ConsoleLandingScreen
import okhttp3.HttpUrl.Companion.toHttpUrl

class MainActivity : FragmentActivity() {
    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent); setIntent(intent)
        au.mainspring.nativeapp.DeepLinkInbox.offer(intent.data?.toString())
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        TokenStore.init(applicationContext)
        au.mainspring.nativeapp.ui.DesignPreferences.init(applicationContext)
        au.mainspring.nativeapp.ConnectivityMonitor.init(applicationContext)
        au.mainspring.nativeapp.ui.RecentItems.init(applicationContext)
        au.mainspring.nativeapp.offline.OfflineSync.start()
        if (savedInstanceState == null) AppLock.onColdStart()
        lifecycle.addObserver(androidx.lifecycle.LifecycleEventObserver { _, event ->
            if(event == androidx.lifecycle.Lifecycle.Event.ON_STOP) AppLock.onBackground()
            if(event == androidx.lifecycle.Lifecycle.Event.ON_START) AppLock.onForeground()
        })
        if (savedInstanceState == null) au.mainspring.nativeapp.DeepLinkInbox.offer(intent?.data?.toString())
        setContent {
            MainspringTheme {
                Surface(Modifier.fillMaxSize()) {
                    val authVm: AuthViewModel = viewModel(factory = AuthViewModelFactory(application))
                    val authState by authVm.state.collectAsStateWithLifecycle()
                    val appLocked by AppLock.locked.collectAsStateWithLifecycle()
                    androidx.compose.foundation.layout.Box(Modifier.fillMaxSize()) {
                    if (authState.loggedIn) {
                        key(authState.sessionKey) {
                        if(authState.consoleOnly) ConsoleLandingScreen(authState,authVm::switchSite,onOpenWeb = {
                            val url = au.mainspring.nativeapp.api.ApiClient.getEffectiveBaseUrl().toHttpUrl().newBuilder().encodedPath("/dashboard").query(null).fragment(null).build().toString()
                            try { startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW,android.net.Uri.parse(url))) }
                            catch(_: android.content.ActivityNotFoundException) { android.widget.Toast.makeText(this@MainActivity,"No browser is available on this device.",android.widget.Toast.LENGTH_LONG).show() }
                        },onLogout = authVm::logout)
                        else if(authState.loggedIn && authState.signupPaymentPending) au.mainspring.nativeapp.ui.screens.SubscriptionRequiredScreen(onOpenWeb = {
                            val url = au.mainspring.nativeapp.api.ApiClient.getEffectiveBaseUrl() + "subscription-required"
                            try { startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW,android.net.Uri.parse(url))) }
                            catch(_: android.content.ActivityNotFoundException) { android.widget.Toast.makeText(this@MainActivity,"No browser is available on this device.",android.widget.Toast.LENGTH_LONG).show() }
                        }, onSignOut = authVm::logout)
                        else
                        MainspringAppShell(
                            sessionSummary = authState.sessionSummary,
                            apiBaseUrl = au.mainspring.nativeapp.api.ApiClient.getEffectiveBaseUrl(),
                            onLogout = { authVm.logout() },
                            features = authState.features,
                            sites = authState.sites,
                            activeSiteId = authState.activeSiteId,
                            onSwitchSite = authVm::switchSite,
                            sessionError = authState.error,
                            subscriptionStatus = authState.subscriptionStatus,
                            trialEnd = authState.trialEnd,
                            sessionRole = authState.role,
                        )
                        }
                        if(authState.loading) androidx.compose.material3.AlertDialog(onDismissRequest = {}, title = { Text("Switching shop…") },
                            text = { androidx.compose.material3.CircularProgressIndicator() }, confirmButton = {})
                    } else {
                        LoginScreen(
                            state = authState,
                            apiBaseUrl = au.mainspring.nativeapp.api.ApiClient.getEffectiveBaseUrl(),
                            onLogin = { slug, email, pass, serverUrl -> authVm.login(slug, email, pass, serverUrl) },
                        )
                    }
                    if(authState.loggedIn && appLocked) au.mainspring.nativeapp.ui.screens.AppLockOverlay(onUnlock = AppLock::unlocked, onSignOut = { AppLock.unlocked(); authVm.logout() })
                    }
                }
            }
        }
    }
}
