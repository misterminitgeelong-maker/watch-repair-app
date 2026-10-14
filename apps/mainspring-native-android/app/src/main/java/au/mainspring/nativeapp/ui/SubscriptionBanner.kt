package au.mainspring.nativeapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import java.time.Instant

/** What the subscription banner should say, separated from the UI so it can be tested. */
sealed class SubscriptionNotice {
    data class TrialEnding(val daysLeft: Int) : SubscriptionNotice()
    object PaymentPastDue : SubscriptionNotice()
}

/** Mirrors the web `SubscriptionBanner`: trial days left, or a past-due warning. Hidden for platform admins. */
fun subscriptionNotice(subscriptionStatus: String?, trialEnd: String?, role: String?, now: Instant = Instant.now()): SubscriptionNotice? {
    if(subscriptionStatus.isNullOrBlank() || role == "platform_admin") return null
    if(subscriptionStatus == "trialing" && !trialEnd.isNullOrBlank()) {
        val end = try { Instant.parse(trialEnd) } catch(_: Exception) { return null }
        val seconds = end.epochSecond - now.epochSecond
        val days = Math.floorDiv(seconds + 86_399, 86_400L).toInt() // ceil, like the web banner
        return if(days <= 0) null else SubscriptionNotice.TrialEnding(days)
    }
    if(subscriptionStatus == "past_due") return SubscriptionNotice.PaymentPastDue
    return null
}

/**
 * Calibre-styled notice for the top of the shell. Billing is managed on the web (store policy), so this only informs.
 * Pass the values from the session (`AuthUiState.subscriptionStatus`, `trialEnd`, `role`).
 */
@Composable fun SubscriptionBanner(subscriptionStatus: String?, trialEnd: String?, role: String?, modifier: Modifier = Modifier) {
    val notice = subscriptionNotice(subscriptionStatus, trialEnd, role) ?: return
    val (label, message, container, content) = when(notice) {
        is SubscriptionNotice.TrialEnding -> Quad(
            "FREE TRIAL / ${notice.daysLeft} DAY${if(notice.daysLeft == 1) "" else "S"} LEFT",
            "Add a payment method on the web app to keep access after the trial ends.",
            Calibre.ForestMint, Calibre.Forest)
        SubscriptionNotice.PaymentPastDue -> Quad(
            "PAYMENT FAILED",
            "Update your billing details on the web app to avoid losing access.",
            MaterialTheme.colorScheme.errorContainer, MaterialTheme.colorScheme.onErrorContainer)
    }
    Surface(modifier.fillMaxWidth(), color = container, contentColor = content, shape = MaterialTheme.shapes.small,
        border = BorderStroke(1.dp, Calibre.Hairline)) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            MonoLabel(label, color = content)
            Text(message, style = MaterialTheme.typography.bodySmall)
        }
    }
}

private data class Quad<A, B, C, D>(val a: A, val b: B, val c: C, val d: D)
