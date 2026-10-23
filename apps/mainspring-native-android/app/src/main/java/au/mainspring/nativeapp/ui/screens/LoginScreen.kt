package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.selection.toggleable
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.platform.testTag
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
import au.mainspring.nativeapp.BuildConfig
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
    var email by rememberSaveable { mutableStateOf(if(state.sessionEnded) LoginPrefs.lastEmail() else "") }
    var password by remember { mutableStateOf("") }
    var serverUrl by remember { mutableStateOf(ApiClient.getEffectiveBaseUrl()) }
    var showServerConfig by remember { mutableStateOf(false) }
    var showPassword by remember { mutableStateOf(false) }
    val submit = { LoginPrefs.save(slug, rememberShop); LoginPrefs.saveEmail(email); onLogin(slug, email, password, serverUrl) }

    // Web login look: cream page, one paper card with a thin ink border and square corners, serif title, red-orange accent.
    val cream = androidx.compose.ui.graphics.Color(0xFFEBE6DC); val paper = androidx.compose.ui.graphics.Color(0xFFF7F7F4)
    val ink = androidx.compose.ui.graphics.Color(0xFF0A0A0A); val accent = androidx.compose.ui.graphics.Color(0xFFE8452A)
    val muted = androidx.compose.ui.graphics.Color(0xFF5B574F)
    val loginField = androidx.compose.material3.OutlinedTextFieldDefaults.colors(
        focusedContainerColor = androidx.compose.ui.graphics.Color.White, unfocusedContainerColor = androidx.compose.ui.graphics.Color.White, disabledContainerColor = androidx.compose.ui.graphics.Color.White,
        focusedBorderColor = ink, unfocusedBorderColor = ink, disabledBorderColor = ink.copy(alpha = 0.4f),
        focusedTextColor = ink, unfocusedTextColor = ink, disabledTextColor = muted,
        focusedLabelColor = muted, unfocusedLabelColor = muted, disabledLabelColor = muted, cursorColor = ink)
    val square = androidx.compose.ui.graphics.RectangleShape
    // Pointing the app at another server is for developers: debug builds that are not aimed at the live site (so the phone test APK for mainspring.au hides it too).
    val canConfigureServer = BuildConfig.DEBUG && !BuildConfig.API_BASE_URL.startsWith("https://mainspring.au")

    androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().background(cream)) {
    Column(
        Modifier
            .fillMaxSize()
            .statusBarsPadding()
            .navigationBarsPadding()
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        androidx.compose.foundation.layout.Box(Modifier.size(56.dp).background(accent, androidx.compose.foundation.shape.CircleShape).semantics { contentDescription = "Mainspring logo" }, contentAlignment = Alignment.Center) {
            Text("M", style = au.mainspring.nativeapp.ui.calibreDisplayStyle(MaterialTheme.typography.headlineMedium), color = androidx.compose.ui.graphics.Color.White)
        }
        Spacer(Modifier.height(12.dp))
        Text("Mainspring", Modifier.semantics { heading() }, style = au.mainspring.nativeapp.ui.calibreDisplayStyle(MaterialTheme.typography.displaySmall), color = ink)
        if(state.sessionEnded) {
            Text("Welcome back", Modifier.padding(top = 4.dp).semantics { heading() }.testTag("welcome-back"), style = MaterialTheme.typography.titleMedium, color = ink)
            Text("It has been a while, so please sign in again. Your shop ID is filled in and your drafts are kept.", Modifier.padding(top = 2.dp), style = MaterialTheme.typography.bodyMedium, color = muted, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        } else Text("Sign in to your shop", Modifier.padding(top = 2.dp), style = MaterialTheme.typography.bodyMedium, color = muted)
        Spacer(Modifier.height(18.dp))

        androidx.compose.material3.Surface(Modifier.fillMaxWidth().widthIn(max = 460.dp), color = paper, shape = square, border = androidx.compose.foundation.BorderStroke(1.dp, ink)) {
            Column(Modifier.padding(horizontal = 16.dp, vertical = 18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if(canConfigureServer && showServerConfig) {
                    au.mainspring.nativeapp.ui.AtelierTextField(
                        value = serverUrl, onValueChange = { serverUrl = it }, label = { Text("Server Base URL") }, singleLine = true,
                        modifier = Modifier.fillMaxWidth(), supportingText = { Text("Example: http://10.0.2.2:8000/ or https://mainspring.au") }, shape = square, colors = loginField,
                    )
                }
                au.mainspring.nativeapp.ui.AtelierTextField(
                    value = slug, onValueChange = { slug = it }, label = { Text("Shop ID (optional)") },
                    supportingText = { Text("Leave blank to sign in using email and password across your shops.", color = muted) },
                    enabled = !state.loading, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next), singleLine = true,
                    modifier = Modifier.fillMaxWidth(), shape = square, colors = loginField,
                )
                Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).toggleable(value = rememberShop, enabled = !state.loading, role = Role.Checkbox, onValueChange = { rememberShop = it }), verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = rememberShop, onCheckedChange = null, enabled = !state.loading, colors = androidx.compose.material3.CheckboxDefaults.colors(checkedColor = accent, checkmarkColor = androidx.compose.ui.graphics.Color.White, uncheckedColor = ink))
                    Text("Remember shop ID", style = MaterialTheme.typography.bodyMedium, color = ink)
                }
                au.mainspring.nativeapp.ui.AtelierTextField(
                    value = email, onValueChange = { email = it }, label = { Text("Email") }, enabled = !state.loading,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next), singleLine = true,
                    modifier = Modifier.fillMaxWidth(), shape = square, colors = loginField,
                )
                au.mainspring.nativeapp.ui.AtelierTextField(
                    value = password, onValueChange = { password = it }, label = { Text("Password") }, enabled = !state.loading,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { if(!state.loading && email.isNotBlank() && password.isNotBlank()) submit() }),
                    singleLine = true,
                    visualTransformation = if(showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = { TextButton(onClick = { showPassword = !showPassword }) { Text(if(showPassword) "Hide" else "Show", color = androidx.compose.ui.graphics.Color(0xFFB32D16)) } },
                    modifier = Modifier.fillMaxWidth(), shape = square, colors = loginField,
                )
                state.error?.let {
                    au.mainspring.nativeapp.ui.ErrorBanner(it) // announced as an assertive live region
                }
                Button(
                    onClick = { submit() },
                    enabled = !state.loading && email.isNotBlank() && password.isNotBlank(),
                    modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
                    shape = square,
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = accent, contentColor = androidx.compose.ui.graphics.Color.White,
                        disabledContainerColor = accent.copy(alpha = 0.45f), disabledContentColor = androidx.compose.ui.graphics.Color.White),
                    elevation = null,
                ) {
                    if (state.loading) {
                        CircularProgressIndicator(
                            modifier = Modifier.height(22.dp).semantics { contentDescription = "Signing in" },
                            strokeWidth = 2.dp, color = androidx.compose.ui.graphics.Color.White,
                        )
                    } else {
                        Text("Sign in", style = MaterialTheme.typography.titleMedium)
                    }
                }
            }
        }
        // Developer-only: pointing the app at another server. Not shown in release builds.
        if(canConfigureServer) TextButton(onClick = { showServerConfig = !showServerConfig }) {
            Text(if (showServerConfig) "Hide connection settings" else "Connection settings", color = muted)
        }
    }
    }
}
