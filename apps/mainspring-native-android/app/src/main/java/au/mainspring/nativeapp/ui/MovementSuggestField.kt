package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.userMessage
import kotlinx.coroutines.CancellationException

/** A manually editable movement field plus catalogue suggestions, matching the web's name/key search. */
@Composable fun MovementSuggestField(value: String, onChange: (String) -> Unit, enabled: Boolean, modifier: Modifier = Modifier) {
    var open by remember { mutableStateOf(false) }
    var rows by remember { mutableStateOf<List<CatalogueMovement>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var query by remember { mutableStateOf("") }
    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        AtelierTextField(value, onChange, label = { Text("Movement") }, enabled = enabled, modifier = Modifier.fillMaxWidth())
        TextButton({ query = value; open = true }, enabled = enabled, modifier = Modifier.testTag("movement-catalogue")) { Text("Find movement in catalogue") }
    }
    LaunchedEffect(open) {
        if(open && rows.isEmpty()) {
            loading = true
            try { rows = ApiClient.service(CatalogueApi::class.java).watchMovements().movements; error = null }
            catch(e: CancellationException) { throw e } catch(e: Exception) { error = e.userMessage() }
            finally { loading = false }
        }
    }
    if(open) AlertDialog(onDismissRequest = { open = false }, title = { Text("Watch movement") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            AtelierTextField(query, { query = it }, label = { Text("Search name or movement key") }, modifier = Modifier.fillMaxWidth().testTag("movement-query"))
            if(loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            error?.let { ErrorBanner(it) }
            val shown = rows.filter { it.name.contains(query.trim(), true) || it.key.contains(query.trim(), true) }.take(30)
            Column(Modifier.heightIn(max = 320.dp).verticalScroll(rememberScrollState())) {
                shown.forEach { row -> TextButton({ onChange(row.name); open = false }, Modifier.fillMaxWidth().testTag("movement-pick-${row.key}")) { Text(row.name, Modifier.weight(1f)); row.quoteCents?.let { Text(formatCents(it, au.mainspring.nativeapp.TokenStore.shopValue("currency") ?: "AUD")) } } }
                if(!loading && shown.isEmpty()) Text("No movements match. You can still type the movement manually.")
            }
        }
    }, confirmButton = { TextButton({ open = false }) { Text("Close") } })
}
