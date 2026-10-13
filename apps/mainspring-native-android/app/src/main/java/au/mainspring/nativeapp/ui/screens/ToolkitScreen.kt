package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ToolkitViewModel
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun ToolkitScreen(onBack: () -> Unit, vm: ToolkitViewModel = viewModel()) {
 val state by vm.state.collectAsStateWithLifecycle(); var search by rememberSaveable { mutableStateOf("") }
 val dirty = state.selected != state.saved
 Scaffold(topBar = { TopAppBar(title = { Text("Shop toolkit", style = MaterialTheme.typography.headlineSmall) }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
  LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
   item {
    Text("This selection is shared by the shop. Check the tools in your vehicle before taking a job.")
    if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    Text("${state.selected.size} tools selected${if(dirty) " · unsaved draft" else " · saved selection"}")
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
     Button(onClick = vm::save, enabled = dirty && !state.loading && !state.busy) { Text("Save selection") }
     OutlinedButton(onClick = vm::discard, enabled = dirty && !state.busy) { Text("Discard draft") }
    }
    OutlinedButton(onClick = vm::load, enabled = !state.loading && !state.busy) { Text("Refresh toolkit") }
    OutlinedTextField(search, { search = it }, label = { Text("Find a tool") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
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
   state.catalog?.groups?.forEach { group ->
    val tools = group.tools.filter { search.isBlank() || "${it.name} ${it.notes.orEmpty()}".contains(search, true) }
    if(tools.isNotEmpty()) {
     item { au.mainspring.nativeapp.ui.SectionLabel("${group.label} · ${group.tools.count {it.key in state.selected}} of ${group.tools.size}") }
     items(tools, key = { it.key }) { tool -> Row { Checkbox(tool.key in state.selected, { vm.toggle(tool.key) }, enabled = !state.busy)
      Column(Modifier.weight(1f).padding(vertical = 8.dp)) { Text(tool.name); tool.notes?.let { Text(it, style = MaterialTheme.typography.bodySmall) } }
     } }
    }
   }
  }
 }
}
