package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.userMessage

/** HQ notices contain their full text in the inbox event; no conversation or customer record is linked. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun HqAlertScreen(id: String, onBack: () -> Unit) {
    var event by remember { mutableStateOf<TenantEventLogRead?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(id) { try {
        var offset = 0
        while(event == null) {
            val page = ApiClient.api.listInbox(100, offset)
            event = page.firstOrNull { it.id == id && it.eventType == "hq_message" }
            if(page.size < 100) break
            offset += page.size
        }
        if(event == null) error = "This notice is no longer in your inbox."
    } catch(e: Exception) { error = e.userMessage() } }
    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Message from Support Office") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
        Column(Modifier.padding(padding).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            event?.let { Text(it.eventSummary, style = MaterialTheme.typography.bodyLarge); Text(au.mainspring.nativeapp.ui.formatShopDate(it.createdAt)) }
            if(event == null && error == null) CircularProgressIndicator()
            error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
        }
    }
}
