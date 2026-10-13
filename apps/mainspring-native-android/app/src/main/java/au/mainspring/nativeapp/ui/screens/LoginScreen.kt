package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.AuthUiState
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.ApiClient

@Composable
fun LoginScreen(
    state: AuthUiState,
    apiBaseUrl: String,
    onLogin: (String, String, String, String) -> Unit,
) {
    var slug by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var serverUrl by remember { mutableStateOf(ApiClient.getEffectiveBaseUrl()) }
    var showServerConfig by remember { mutableStateOf(false) }
    var showPassword by remember { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .navigationBarsPadding()
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(40.dp))
        androidx.compose.foundation.Image(androidx.compose.ui.res.painterResource(au.mainspring.nativeapp.R.drawable.ic_launcher_vector), contentDescription = "Mainspring logo", modifier = Modifier.size(88.dp))
        Text("Mainspring", style = MaterialTheme.typography.headlineMedium)
        Text("Sign in to your shop", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)

        if (showServerConfig) {
            au.mainspring.nativeapp.ui.AtelierTextField(
                value = serverUrl,
                onValueChange = { serverUrl = it },
                label = { Text("Server Base URL") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                supportingText = { Text("Example: http://10.0.2.2:8000/ or https://mainspring.au") },
            )
        }

        Spacer(Modifier.height(16.dp))
        au.mainspring.nativeapp.ui.AtelierTextField(
            value = slug,
            onValueChange = { slug = it },
            label = { Text("Shop ID (optional)") },
            supportingText = { Text("Leave blank to sign in using email and password across your shops.") },
            enabled = !state.loading,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        au.mainspring.nativeapp.ui.AtelierTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Email") },
            enabled = !state.loading,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        au.mainspring.nativeapp.ui.AtelierTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            enabled = !state.loading,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { if(!state.loading && email.isNotBlank() && password.isNotBlank()) onLogin(slug,email,password,serverUrl) }),
            singleLine = true,
            visualTransformation = if(showPassword) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = { TextButton(onClick = { showPassword = !showPassword }) { Text(if(showPassword) "Hide" else "Show") } },
            modifier = Modifier.fillMaxWidth(),
        )
        state.error?.let {
            au.mainspring.nativeapp.ui.ErrorBanner(it)
        }
        Button(
            onClick = { onLogin(slug, email, password, serverUrl) },
            enabled = !state.loading && email.isNotBlank() && password.isNotBlank(),
            modifier = Modifier.fillMaxWidth().height(52.dp),
        ) {
            if (state.loading) {
                CircularProgressIndicator(
                    modifier = Modifier.height(22.dp),
                    strokeWidth = 2.dp,
                )
            } else {
                Text("Sign in", style = MaterialTheme.typography.titleMedium)
            }
        }
        TextButton(onClick = { showServerConfig = !showServerConfig }) {
            Text(if (showServerConfig) "Hide connection settings" else "Connection settings")
        }
    }
}
