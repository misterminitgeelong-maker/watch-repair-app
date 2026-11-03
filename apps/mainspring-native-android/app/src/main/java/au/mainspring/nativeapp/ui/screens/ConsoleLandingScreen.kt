package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.AuthUiState

@Composable
fun ConsoleLandingScreen(state: AuthUiState, onSwitchSite: (String) -> Unit, onOpenWeb: () -> Unit, onLogout: () -> Unit) {
    Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(24.dp),verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Choose a shop",style = MaterialTheme.typography.headlineMedium)
        state.sessionSummary?.let { Text(it) }
        Text("Open a shop for native counter and field workflows. HQ and platform controls are available in the web console.")
        state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
        state.sites.filter { it.tenantId != state.activeSiteId }.forEach { site ->
            OutlinedButton(onClick = { onSwitchSite(site.tenantId) },enabled = !state.loading,modifier = Modifier.fillMaxWidth()) { Text("Open ${site.name}") }
        }
        Button(onClick = onOpenWeb,enabled = !state.loading) { Text("Open web console") }
        TextButton(onClick = onLogout,enabled = !state.loading) { Text("Sign out") }
    }
}
