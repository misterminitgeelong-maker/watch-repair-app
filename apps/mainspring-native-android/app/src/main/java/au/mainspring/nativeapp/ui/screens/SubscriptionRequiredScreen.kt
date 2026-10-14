package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.ui.MonoLabel
import au.mainspring.nativeapp.ui.PrimaryAction
import au.mainspring.nativeapp.ui.SecondaryAction

/**
 * Blocking screen for shops whose signup payment is still pending (`signup_payment_pending`).
 * The native app deliberately has no billing UI, so this only explains and opens the web checkout.
 * `onOpenWeb` should open `<server>/subscription-required` in the browser.
 */
@Composable fun SubscriptionRequiredScreen(onOpenWeb: () -> Unit, onSignOut: () -> Unit) {
    Column(
        Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        MonoLabel("Subscription")
        Spacer(Modifier.height(8.dp))
        Text("Finish setting up your subscription", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(12.dp))
        Text(
            "Your shop was created, but the payment was not completed. Finish checkout on the Mainspring web app to unlock your shop. " +
                "Billing is not available inside this app.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(24.dp))
        PrimaryAction(onOpenWeb, Modifier.fillMaxWidth()) { Text("Continue on the web") }
        Spacer(Modifier.height(8.dp))
        SecondaryAction(onSignOut, Modifier.fillMaxWidth()) { Text("Sign out") }
        Spacer(Modifier.height(16.dp))
        Text("Already paid? Sign out and sign back in to refresh.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
