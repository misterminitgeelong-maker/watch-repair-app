package au.mainspring.nativeapp.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.watchBrandSuggestions

/** "Watch 2 · Ticket #1043" (or just "Watch 2" before the number is known). [index] is zero-based. */
fun intakeTicketLabel(index: Int, number: String?, noun: String = "Watch"): String {
    val clean = number?.trim()?.removePrefix("#")?.trim().orEmpty()
    return "$noun ${index + 1}" + if(clean.isEmpty()) "" else " · Ticket #$clean"
}

/** Web page URL on the same origin as the API (the app serves the web UI from the API host), as for intake status links. */
fun webPageUrl(apiBaseUrl: String, path: String): String {
    val uri = try { java.net.URI(apiBaseUrl.trim()) } catch(e: Exception) { null }
    val origin = if(uri?.scheme != null && uri.host != null) "${uri.scheme}://${uri.host}" + (if(uri.port != -1) ":${uri.port}" else "") else apiBaseUrl.trim().trimEnd('/')
    return origin + "/" + path.trimStart('/')
}

/** Opens [url] in the browser; returns an error message or null. */
fun openWebPage(context: Context, url: String): String? = try {
    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); null
} catch(e: Exception) { "No browser available to open the web app." }

/** A row linking out to a web-app page for setup that is not built into the app. */
@Composable fun FinishOnWebRow(title: String, detail: String, path: String, tag: String) {
    val context = LocalContext.current
    var error by remember { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(title, style = MaterialTheme.typography.titleSmall)
        Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        TextButton({ error = openWebPage(context, webPageUrl(au.mainspring.nativeapp.api.ApiClient.getEffectiveBaseUrl(), path)) },
            Modifier.heightIn(min = 48.dp).testTag(tag)) { Text("Finish on the web") }
        error?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
    }
}

/** Text field with tappable brand suggestions (the web BrandAutocomplete) while it has focus. */
@Composable fun BrandSuggestField(label: String, value: String, onChange: (String) -> Unit, enabled: Boolean, placeholder: String?, tag: String = "brand-field") {
    var focused by remember { mutableStateOf(false) }
    val suggestions = if(focused && enabled) watchBrandSuggestions(value, 8) else emptyList()
    Column(Modifier.fillMaxWidth().onFocusChanged { focused = it.hasFocus }.testTag(tag), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        WizardField(label, value, onChange, placeholder = placeholder, enabled = enabled, modifier = Modifier.fillMaxWidth())
        if(suggestions.isNotEmpty()) Row(Modifier.horizontalScroll(rememberScrollState()).testTag("$tag-suggestions"), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            suggestions.forEach { b -> AtelierChip(selected = false, onClick = { onChange(b) }, label = { Text(b) }) }
        }
    }
}
