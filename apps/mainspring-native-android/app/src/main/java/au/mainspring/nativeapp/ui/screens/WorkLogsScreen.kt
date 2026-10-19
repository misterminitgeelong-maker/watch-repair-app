package au.mainspring.nativeapp.ui.screens
import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun WorkLogsScreen(jobId: String, onBack: () -> Unit, vm: WorkLogsViewModel = viewModel(key = jobId, factory = WorkLogsViewModel.factory(jobId))) {
 val state by vm.state.collectAsStateWithLifecycle()
 Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Work logs") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack) }) }) { padding ->
  LazyColumn(Modifier.padding(padding).fillMaxSize().imePadding(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
   item {
    if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth()); state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
    androidx.compose.material3.TextButton(onClick = vm::refresh, enabled = !state.loading && !state.busy) { Text("Refresh") }
    if(state.uncertain) OutlinedButton(onClick = vm::checkedHistory, enabled = !state.loading && state.historyChecked) { Text("I checked for this work log") }
    Text("${state.rows.sumOf { it.minutes }} minutes logged", style = MaterialTheme.typography.titleMedium)
    au.mainspring.nativeapp.ui.AtelierTextField(state.note, vm::note, label = { Text("Work completed") }, modifier = Modifier.fillMaxWidth(), enabled = !state.busy)
    au.mainspring.nativeapp.ui.AtelierTextField(state.minutes, vm::minutes, label = { Text("Minutes spent") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth(), enabled = !state.busy, singleLine = true)
    Button(onClick = vm::save, enabled = !state.loading && !state.busy && !state.uncertain) { Text("Save work log") }
   }
   items(state.rows, key = { it.id }) { row -> Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp)) {
    Text("${row.minutes} min · ${au.mainspring.nativeapp.ui.formatShopDate(row.createdAt, TokenStore.calendarTimezone())}"); row.note?.let { Text(it) }
   } } }
  }
 }
}
