package au.mainspring.nativeapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        TokenStore.init(applicationContext)
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) {
                    val vm: AuthViewModel = viewModel(factory = AuthViewModelFactory(application))
                    val state by vm.state.collectAsStateWithLifecycle()
                    NativeRoot(
                        state = state,
                        apiBaseUrl = BuildConfig.API_BASE_URL,
                        onLogin = { slug, email, pass -> vm.login(slug, email, pass) },
                        onLogout = { vm.logout() },
                    )
                }
            }
        }
    }
}

@Composable
private fun NativeRoot(
    state: AuthUiState,
    apiBaseUrl: String,
    onLogin: (String, String, String) -> Unit,
    onLogout: () -> Unit,
) {
    var slug by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    Column(
        Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Mainspring (native)", style = MaterialTheme.typography.headlineSmall)
        Text(
            "API: $apiBaseUrl",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(8.dp))

        if (state.loggedIn) {
            Text("Signed in", style = MaterialTheme.typography.titleMedium)
            state.sessionSummary?.let { Text(it) }
            Spacer(Modifier.height(16.dp))
            Button(onClick = onLogout) { Text("Sign out") }
            Text(
                "This is a separate native shell from the Capacitor app. Add screens here as you port features.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            OutlinedTextField(
                value = slug,
                onValueChange = { slug = it },
                label = { Text("Shop ID") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Email") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("Password") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
            )
            state.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            Button(
                onClick = { onLogin(slug, email, password) },
                enabled = !state.loading && slug.isNotBlank() && email.isNotBlank() && password.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (state.loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(22.dp),
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text("Sign in")
                }
            }
        }
    }
}
