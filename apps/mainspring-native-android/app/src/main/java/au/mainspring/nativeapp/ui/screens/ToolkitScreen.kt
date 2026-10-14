package au.mainspring.nativeapp.ui.screens
import androidx.compose.foundation.clickable
import au.mainspring.nativeapp.ui.screens.LinkAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ToolkitViewModel
@Composable private fun ShopSettingsSection(s: au.mainspring.nativeapp.ToolkitSettingsState, vm: ToolkitViewModel) {
 Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
  au.mainspring.nativeapp.ui.SectionLabel("Settings")
  if(s.loading || s.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
  s.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, onRetry = if(!s.loaded) vm::loadSettings else null) }
  if(!s.loaded) return@Column
  if(!s.canEditNotifications) Text("Only an owner or manager can change these settings.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
  au.mainspring.nativeapp.ui.FlatPanel {
   Row(Modifier.fillMaxWidth().heightIn(min = 56.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
    Column(Modifier.weight(1f)) {
     Text("Customer SMS", style = MaterialTheme.typography.bodyLarge)
     Text("Text customers when a technician is on the way or has arrived.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    Switch(s.smsEnabled, { vm.setSms(it) }, enabled = s.canEditNotifications && !s.busy, modifier = Modifier.semantics { contentDescription = "Customer SMS" })
   }
   au.mainspring.nativeapp.ui.AtelierTextField(s.phoneDraft, vm::phoneDraft, label = { Text("Dispatch phone") }, singleLine = true, readOnly = !s.canEditNotifications,
    enabled = !s.busy, supportingText = { Text("Receives shop booking alerts.") },
    keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Phone), modifier = Modifier.fillMaxWidth())
   if(s.canEditNotifications) Button(onClick = vm::saveDispatchPhone, enabled = !s.busy && s.phoneDraft.trim() != s.dispatchPhone, modifier = Modifier.heightIn(min = 48.dp)) { Text("Save dispatch phone") }
  }
  au.mainspring.nativeapp.ui.SectionLabel("POS catalogue categories")
  if(!s.canEditCatalogue) Text("Only the owner can change the catalogue categories.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
  s.availableCategories.forEach { category ->
   Row(Modifier.fillMaxWidth().clickable(enabled = s.canEditCatalogue && !s.busy) { vm.toggleCategory(category.key) }.heightIn(min = 56.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
    Checkbox(category.key in s.enabledCategories, { vm.toggleCategory(category.key) }, enabled = s.canEditCatalogue && !s.busy, modifier = Modifier.semantics { contentDescription = category.label })
    Column(Modifier.weight(1f).padding(vertical = 8.dp)) {
     Text(category.label.ifBlank { category.key }, style = MaterialTheme.typography.bodyLarge)
     if(category.description.isNotBlank()) Text(category.description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
   }
  }
 }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun ToolkitScreen(onBack: () -> Unit, vm: ToolkitViewModel = viewModel()) {
 val state by vm.state.collectAsStateWithLifecycle(); val settings by vm.settings.collectAsStateWithLifecycle(); var search by rememberSaveable { mutableStateOf("") }
 val dirty = state.selected != state.saved
 Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Shop toolkit") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) },
   actions = { TextButton(onClick = vm::load, enabled = !state.loading && !state.busy, modifier = Modifier.heightIn(min = 48.dp)) { Text("Refresh") } }) },
  bottomBar = { if(dirty) Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = if(au.mainspring.nativeapp.ui.LocalCalibre.current) 0.dp else 2.dp) {
   if(au.mainspring.nativeapp.ui.LocalCalibre.current) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
   Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
    OutlinedButton(onClick = vm::discard, enabled = !state.busy, modifier = Modifier.weight(1f).heightIn(min = 52.dp)) { Text("Discard draft") }
    Button(onClick = vm::save, enabled = !state.loading && !state.busy, modifier = Modifier.weight(1.5f).heightIn(min = 52.dp)) { Text("Save selection") }
   } } }) { padding ->
  LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
   item {
    Text("This selection is shared by the shop. Check the tools in your vehicle before taking a job.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
    if(au.mainspring.nativeapp.ui.LocalCalibre.current) au.mainspring.nativeapp.ui.MonoLabel("Shop toolkit")
    Text("${state.selected.size} tools selected${if(dirty) " · unsaved draft" else " · saved selection"}", style = if(au.mainspring.nativeapp.ui.LocalCalibre.current) MaterialTheme.typography.headlineSmall else MaterialTheme.typography.titleMedium)
    au.mainspring.nativeapp.ui.AtelierTextField(search, { search = it }, label = { Text("Find a tool") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
   }
   item { au.mainspring.nativeapp.ui.SectionLabel("What's the job?")
    Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
     state.catalog?.scenarios?.forEach {scenario->OutlinedButton({vm.checkScenario(scenario.id)},enabled=!state.busy && !state.loading) {Text(scenario.label)}}
    }
   }
   state.readiness?.let {result->item {au.mainspring.nativeapp.ui.FlatPanel {
    Text(result.label,style=MaterialTheme.typography.titleMedium)
    Text(if(result.ready) "Required tools selected" else "Required tools missing",color=if(result.ready) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.primary)
    result.missing.forEach {Text("Missing: ${it.name}",style=MaterialTheme.typography.bodySmall)}
    result.nice.forEach {Text("Optional: ${it.name}",style=MaterialTheme.typography.bodySmall)}
    result.tips?.let {Text(it,style=MaterialTheme.typography.bodySmall)}
   } } }
   item { ShopSettingsSection(settings, vm) }
   state.catalog?.groups?.forEach { group ->
    val tools = group.tools.filter { search.isBlank() || "${it.name} ${it.notes.orEmpty()}".contains(search, true) }
    if(tools.isNotEmpty()) {
     item { au.mainspring.nativeapp.ui.SectionLabel("${group.label} · ${group.tools.count {it.key in state.selected}} of ${group.tools.size}") }
     items(tools, key = { it.key }) { tool -> val calibre = au.mainspring.nativeapp.ui.LocalCalibre.current
      val body: @Composable () -> Unit = {
      Row(Modifier.fillMaxWidth().clickable(enabled = !state.busy) { vm.toggle(tool.key) }.heightIn(min = 56.dp).padding(end = 12.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
       Checkbox(tool.key in state.selected, { vm.toggle(tool.key) }, enabled = !state.busy, modifier = Modifier.semantics { contentDescription = tool.name })
       Column(Modifier.weight(1f).padding(vertical = 8.dp)) { Text(tool.name, style = MaterialTheme.typography.bodyLarge); tool.notes?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) } }
      } }
      if(calibre) Column(Modifier.fillMaxWidth()) { body(); HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant) }
      else Surface(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) { body() } }
    }
   }
  }
 }
}
