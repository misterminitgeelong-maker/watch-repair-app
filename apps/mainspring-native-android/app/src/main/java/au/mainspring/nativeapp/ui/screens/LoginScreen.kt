package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.selection.toggleable
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
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
import au.mainspring.nativeapp.LoginPrefs
import au.mainspring.nativeapp.TokenStore
import androidx.compose.material3.Checkbox
import au.mainspring.nativeapp.api.ApiClient

@Composable
fun LoginScreen(
    state: AuthUiState,
    apiBaseUrl: String,
    onLogin: (String, String, String, String) -> Unit,
) {
    var slug by rememberSaveable { mutableStateOf(LoginPrefs.rememberedShopId()) }
    var rememberShop by rememberSaveable { mutableStateOf(LoginPrefs.rememberEnabled()) }
    var email by rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var serverUrl by remember { mutableStateOf(ApiClient.getEffectiveBaseUrl()) }
    var showServerConfig by remember { mutableStateOf(false) }
    var showPassword by remember { mutableStateOf(false) }
    val submit = { LoginPrefs.save(slug, rememberShop); onLogin(slug, email, password, serverUrl) }

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
        androidx.compose.foundation.Image(androidx.compose.ui.res.painterResource(au.mainspring.nativeapp.R.drawable.ic_launcher_vector), contentDescription = null, modifier = Modifier.size(88.dp))
        Text("Mainspring", Modifier.semantics { heading() }, style = MaterialTheme.typography.headlineMedium)
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
        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).toggleable(value = rememberShop, enabled = !state.loading, role = Role.Checkbox, onValueChange = { rememberShop = it }), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = rememberShop, onCheckedChange = null, enabled = !state.loading)
            Text("Remember shop ID", style = MaterialTheme.typography.bodyMedium)
        }
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
            keyboardActions = KeyboardActions(onDone = { if(!state.loading && email.isNotBlank() && password.isNotBlank()) submit() }),
            singleLine = true,
            visualTransformation = if(showPassword) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = { TextButton(onClick = { showPassword = !showPassword }) { Text(if(showPassword) "Hide" else "Show") } },
            modifier = Modifier.fillMaxWidth(),
        )
        state.error?.let {
            au.mainspring.nativeapp.ui.ErrorBanner(it) // announced as an assertive live region
        }
        Button(
            onClick = { submit() },
            enabled = !state.loading && email.isNotBlank() && password.isNotBlank(),
            modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
        ) {
            if (state.loading) {
                CircularProgressIndicator(
                    modifier = Modifier.height(22.dp).semantics { contentDescription = "Signing in" },
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
