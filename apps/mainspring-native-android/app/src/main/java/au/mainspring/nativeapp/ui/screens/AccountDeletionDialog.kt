package au.mainspring.nativeapp.ui.screens

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.api.ApiClient

const val DELETION_CONTACT_EMAIL = "admin@mainspring.au"
const val DELETION_SUBJECT = "Mainspring account deletion request"

enum class DeletionScope { OwnLogin, WholeShop }

/** The web `/delete-account` page works by emailing the support address, so the app builds the same request. */
fun deletionRequestBody(scope: DeletionScope, shopName: String?, shopId: String, accountEmail: String): String {
    val what = when(scope) {
        DeletionScope.OwnLogin -> "Delete only my own login and personal information."
        DeletionScope.WholeShop -> "Delete the WHOLE SHOP account, including its customers, jobs, photos and files. I understand this cannot be undone."
    }
    return "Please delete my Mainspring account.\n\n$what\n\nShop ID: $shopId\nShop name: ${shopName.orEmpty()}\nAccount email: $accountEmail\nRequested from: Mainspring Android app (owner)\n"
}

/** What the owner must type before the request can be composed. */
fun deletionConfirmationPhrase(scope: DeletionScope, shopId: String) = if(scope == DeletionScope.WholeShop) shopId.ifBlank { "DELETE" } else "DELETE"

fun deletionConfirmed(scope: DeletionScope, shopId: String, typed: String) =
    typed.trim().equals(deletionConfirmationPhrase(scope, shopId), ignoreCase = true)

/** Owner-only dialog; callers must show it only to the owner. Does not sign out: deletion happens after support verifies the request. */
@Composable fun AccountDeletionDialog(shopName: String?, shopId: String, accountEmail: String, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var scope by remember { mutableStateOf(DeletionScope.OwnLogin) }
    var typed by remember { mutableStateOf("") }
    var notice by remember { mutableStateOf<String?>(null) }
    val phrase = deletionConfirmationPhrase(scope, shopId)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Delete account or shop") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("This sends a deletion request to Mainspring support. We verify it is really you and act within 30 days. Nothing is deleted until then.",
                    style = MaterialTheme.typography.bodySmall)
                au.mainspring.nativeapp.ui.LabeledRadio(scope == DeletionScope.OwnLogin, { scope = DeletionScope.OwnLogin; typed = "" }) {
                    Text("Only my own login and personal details", style = MaterialTheme.typography.bodyMedium)
                }
                au.mainspring.nativeapp.ui.LabeledRadio(scope == DeletionScope.WholeShop, { scope = DeletionScope.WholeShop; typed = "" }) {
                    Text("The whole shop", style = MaterialTheme.typography.bodyMedium)
                }
                if(scope == DeletionScope.WholeShop) Text(
                    "The shop's customers, jobs, photos and files will be deleted and this cannot be undone. Export anything you need first. Invoices and payment records may be kept for the period the law requires.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                OutlinedTextField(typed, { typed = it }, Modifier.fillMaxWidth(), singleLine = true,
                    label = { Text("Type $phrase to confirm") })
                notice?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
                TextButton({
                    val url = ApiClient.getEffectiveBaseUrl().trimEnd('/') + "/delete-account"
                    try { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
                    catch(_: ActivityNotFoundException) { notice = "No browser is available on this device." }
                }) { Text("Read the web deletion page") }
            }
        },
        confirmButton = {
            TextButton(enabled = deletionConfirmed(scope, shopId, typed), onClick = {
                val send = Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:")).apply {
                    putExtra(Intent.EXTRA_EMAIL, arrayOf(DELETION_CONTACT_EMAIL))
                    putExtra(Intent.EXTRA_SUBJECT, DELETION_SUBJECT)
                    putExtra(Intent.EXTRA_TEXT, deletionRequestBody(scope, shopName, shopId, accountEmail))
                }
                try { context.startActivity(send); onDismiss() }
                catch(_: ActivityNotFoundException) { notice = "No email app is available. Email $DELETION_CONTACT_EMAIL from $accountEmail with the subject \"$DELETION_SUBJECT\"." }
            }) { Text("Send request") }
        },
        dismissButton = { TextButton(onDismiss) { Text("Cancel") } },
    )
}
