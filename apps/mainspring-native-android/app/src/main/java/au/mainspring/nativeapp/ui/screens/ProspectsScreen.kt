package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.ProspectLead
import com.google.gson.*
import java.time.*
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun ProspectsScreen(onBack: () -> Unit, vm: ProspectViewModel = viewModel(), embedded: Boolean = false, initialTab: Int = 0) {
 val state by vm.state.collectAsStateWithLifecycle()
 var tab by rememberSaveable { mutableStateOf(initialTab) }; var region by rememberSaveable { mutableStateOf("VIC") }
 var category by rememberSaveable { mutableStateOf("") }; var suburbs by rememberSaveable { mutableStateOf("") }
 var live by rememberSaveable { mutableStateOf(false) }; var query by rememberSaveable { mutableStateOf("") }
 var stage by rememberSaveable { mutableStateOf("") }; var editing by rememberSaveable { mutableStateOf<String?>(null) }
 val enabled = !state.loading && !state.busy
 LaunchedEffect(state.categories) { if(category.isBlank()) category = state.categories.firstOrNull()?.key.orEmpty() }
 Scaffold(contentWindowInsets = if(embedded) WindowInsets(0,0,0,0) else ScaffoldDefaults.contentWindowInsets,topBar = { if(!embedded) TopAppBar(title = { Text("Mobile prospects", style = MaterialTheme.typography.titleLarge) }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
  Column(Modifier.padding(padding).fillMaxSize()) {
   TabRow(tab) { Tab(tab == 0, { tab = 0 }, text = { Text("Prospect board") }); Tab(tab == 1, { tab = 1 }, text = { Text("Find businesses") }) }
   if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
   state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(12.dp)) }
   if(state.uncertainLead.isNotBlank()) {
    Text("A stage change could not be confirmed. Refresh and review the prospect before advancing it again.", modifier = Modifier.padding(12.dp))
    OutlinedButton(onClick = vm::acknowledgeStage, enabled = enabled && state.historyChecked, modifier = Modifier.padding(horizontal = 12.dp)) { Text("I reviewed the current stage") }
   }
   LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
    if(tab == 0) {
     item {
      Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { TextButton(onClick = vm::refresh, enabled = enabled) { Text("Refresh prospects") }; Text("${state.leads.size} prospects") }
      OutlinedTextField(query, { query = it }, label = { Text("Search name, contact or notes") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
      Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
       (listOf("") + listOf("new", "contacted", "visited", "onboarded") + state.leads.map { it.status }).distinct().forEach { value ->
        FilterChip(stage == value, { stage = value }, label = { Text(if(value.isBlank()) "All stages" else value.replace('_', ' ')) })
       }
      }
     }
     val leads = state.leads.filter { (stage.isBlank() || it.status == stage) && (query.isBlank() || "${it.name} ${it.contactName.orEmpty()} ${it.notes.orEmpty()} ${it.phone.orEmpty()}".contains(query, true)) }
     if(enabled && leads.isEmpty()) item { Text("No prospects match this view") }
     items(leads, key = { it.id }) { lead -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
      Text(lead.name, style = MaterialTheme.typography.titleMedium); Text(lead.status.replace('_', ' '))
      lead.address?.let { Text(it) }; lead.contactName?.let { Text("Contact: $it") }; lead.contactEmail?.let { Text(it) }; lead.phone?.let { Text(it) }
      lead.visit?.let { Text("Visit ${au.mainspring.nativeapp.ui.formatShopDate(it, TokenStore.calendarTimezone())}") }
      lead.notes?.let { Text(it) }; if(lead.accountId != null) Text("Linked to a customer account")
      OutlinedButton(onClick = { editing = lead.id }, enabled = enabled) { Text("Open prospect") }
     } } }
    } else {
     item {
      Text("Search your stored business directory or request fresh results.")
      Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
       listOf("ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA").forEach { value -> FilterChip(region == value, { region = value }, label = { Text(value) }) }
      }
      state.categories.forEach { option -> Row { RadioButton(category == option.key, { category = option.key }, enabled = enabled); Text(option.label) } }
      OutlinedTextField(suburbs, { suburbs = it }, label = { Text("Suburbs, separated by commas") }, modifier = Modifier.fillMaxWidth())
      Row { Checkbox(live, { live = it }, enabled = enabled); Text("Request fresh search (up to five suburbs)") }
      Button(onClick = { vm.search(category, region, suburbs, live) }, enabled = enabled && category.isNotBlank()) { Text("Search businesses") }
      state.source?.let { Text(if(it == "stored") "Results from the saved directory" else "Fresh search results") }
     }
     items(state.results, key = { it.placeId }) { business -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
      Text(business.name, style = MaterialTheme.typography.titleMedium); Text(business.address)
      business.phone?.let { Text(it) }; business.website?.let { Text(it) }; business.rating?.let { Text("Rating $it · ${business.reviews ?: 0} reviews") }
      val saved = state.leads.firstOrNull { it.placeId == business.placeId }
      OutlinedButton(onClick = { if(saved == null) vm.save(business, region) else { tab = 0; editing = saved.id } }, enabled = enabled) { Text(if(saved == null) "Save to board" else "Open saved prospect") }
     } } }
     if(state.source != null && state.results.isEmpty() && enabled) item { Text("No businesses found for this search") }
    }
   }
  }
 }
 state.leads.firstOrNull { it.id == editing }?.let { lead -> key(lead.id) { ProspectEditor(lead, vm, enabled, onClose = { editing = null }) } }
}

@Composable private fun ProspectEditor(lead: ProspectLead, vm: ProspectViewModel, enabled: Boolean, onClose: () -> Unit) {
 val state by vm.state.collectAsStateWithLifecycle()
 val drafts = remember(lead.id) { TokenStore.bindDrafts() }
 val raw = remember(lead.id) { drafts.loadMessageDraft("prospect-edit/${lead.id}") }
 val draft = remember(raw) { try { JsonParser.parseString(raw).asJsonObject } catch(_: Exception) { null } }
 fun initial(key: String, fallback: String) = draft?.get(key)?.takeUnless { it.isJsonNull }?.asString ?: fallback
 var name by rememberSaveable { mutableStateOf(initial("name", lead.contactName.orEmpty())) }
 var email by rememberSaveable { mutableStateOf(initial("email", lead.contactEmail.orEmpty())) }
 var notes by rememberSaveable { mutableStateOf(initial("notes", lead.notes.orEmpty())) }
 val localVisit = remember(lead.visit) { try { lead.visit?.let { au.mainspring.nativeapp.ui.scheduleInputDate(it, TokenStore.calendarTimezone()) }.orEmpty() } catch(_: Exception) { lead.visit.orEmpty() } }
 var visit by rememberSaveable { mutableStateOf(initial("visit", localVisit)) }
 var confirmAdvance by remember { mutableStateOf(false) }
 fun persist() { val json = JsonObject().apply { addProperty("name", name); addProperty("email", email); addProperty("notes", notes); addProperty("visit", visit) }; drafts.saveMessageDraft("prospect-edit/${lead.id}", json.toString()) }
 AlertDialog(onDismissRequest = { if(enabled) onClose() }, title = { Text(lead.name) }, text = {
  Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
   state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
   if(state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
   Text("Stage: ${lead.status}")
   OutlinedTextField(name, { name = it; persist() }, label = { Text("Contact name") }, enabled = enabled)
   OutlinedTextField(email, { email = it; persist() }, label = { Text("Contact email") }, enabled = enabled)
   OutlinedTextField(notes, { notes = it; persist() }, label = { Text("Notes") }, enabled = enabled)
   OutlinedTextField(visit, { visit = it; persist() }, label = { Text("Visit (DD/MM/YYYY HH:mm)") }, enabled = enabled)
   Text("Visits use ${TokenStore.calendarTimezone()}. Leaving the visit blank clears it.")
   if(lead.status in listOf("new", "contacted", "visited", "quote_needed", "follow_up_due")) OutlinedButton(onClick = { confirmAdvance = true }, enabled = enabled && state.uncertainLead.isBlank()) { Text("Save and advance stage") }
   Text("Your draft is retained on this device until saved.")
  }
 }, confirmButton = { Button(onClick = { vm.update(lead.id, name, email, notes, visit, false, onClose) }, enabled = enabled) { Text("Save details") } },
 dismissButton = { TextButton(onClick = onClose, enabled = enabled) { Text("Close") } })
 if(confirmAdvance) AlertDialog(onDismissRequest = { confirmAdvance = false }, title = { Text("Advance prospect?", style = MaterialTheme.typography.headlineSmall) }, text = { Text(if(lead.status == "visited") "Save these contact details and create a customer account for this prospect." else "Save these contact details and move this prospect to the next stage.") },
  confirmButton = { Button(onClick = { confirmAdvance = false; vm.update(lead.id, name, email, notes, visit, true, onClose) }, enabled = enabled) { Text("Save and advance") } }, dismissButton = { TextButton(onClick = { confirmAdvance = false }) { Text("Cancel") } })
}
