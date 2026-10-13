package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.TokenStore

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun LeadHubScreen(onBack: () -> Unit,onNavigate: (String) -> Unit) {
    var tab by rememberSaveable {mutableStateOf("inbox")}
    Scaffold(topBar={au.mainspring.nativeapp.ui.AtelierTopAppBar(title={Text("Lead inbox",style=MaterialTheme.typography.titleLarge)},navigationIcon={au.mainspring.nativeapp.ui.BackButton(onBack)},actions={TextButton({onNavigate("bookingRequests")}) {Text("Bookings")}})}) {padding->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal=12.dp),horizontalArrangement=Arrangement.spacedBy(6.dp)) {
                val tabs=listOf("inbox" to "Lead inbox","prospects" to "Prospects","board" to "Board") + if(TokenStore.canManageInvoices()) listOf("team" to "Team") else emptyList()
                tabs.forEach {(key,label)->au.mainspring.nativeapp.ui.AtelierChip(tab==key,{tab=key},label={Text(label)})}
            }
            Box(Modifier.weight(1f)) {key(tab) {when(tab) {
                "prospects" -> ProspectsScreen(onBack,embedded=true,initialTab=1)
                "board" -> ProspectsScreen(onBack,embedded=true,initialTab=0)
                "team" -> TeamScreen(onBack,embedded=true)
                else -> InboxScreen(onBack,embedded=true)
            } } }
        }
    }
}
