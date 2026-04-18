package au.mainspring.nativeapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ui.MainspringAppShell
import au.mainspring.nativeapp.ui.screens.LoginScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        TokenStore.init(applicationContext)
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) {
                    val authVm: AuthViewModel = viewModel(factory = AuthViewModelFactory(application))
                    val authState by authVm.state.collectAsStateWithLifecycle()
                    if (authState.loggedIn) {
                        MainspringAppShell(
                            sessionSummary = authState.sessionSummary,
                            apiBaseUrl = BuildConfig.API_BASE_URL,
                            onLogout = { authVm.logout() },
                        )
                    } else {
                        LoginScreen(
                            state = authState,
                            apiBaseUrl = BuildConfig.API_BASE_URL,
                            onLogin = { slug, email, pass -> authVm.login(slug, email, pass) },
                        )
                    }
                }
            }
        }
    }
}
