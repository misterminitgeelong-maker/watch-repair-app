package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import android.content.Intent
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.ShoeIntakeViewModel
import au.mainspring.nativeapp.ui.PhotoThumbnail
import au.mainspring.nativeapp.ui.formatCents
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShoeIntakeScreen(onBack: () -> Unit, onOpenJob: (String) -> Unit, vm: ShoeIntakeViewModel = viewModel(), preselectedCustomerId: String? = null, onSwitchService: ((String) -> Unit)? = null, services: List<Pair<String, String>> = emptyList()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val step = vm.field("step").toIntOrNull()?.coerceIn(0,3) ?: 0
    var pair by rememberSaveable { mutableIntStateOf(0) }
    var photoPair by rememberSaveable { mutableIntStateOf(0) }
    var cameraUri by rememberSaveable { mutableStateOf("") }
    var leave by remember { mutableStateOf(false) }; var discard by remember { mutableStateOf(false) }
    var reconcile by remember { mutableStateOf(false) }; var photoError by remember { mutableStateOf<String?>(null) }
    val locked = state.busy || vm.field("jobId").isNotBlank() || vm.field("uncertain").isNotBlank() || vm.field("hasAcknowledgement") == "true"
    BackHandler { if(!state.busy) leave = true }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if(uri != null) { try { context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } catch(_: SecurityException) { photoError = "Reselect this photo if access is lost after closing the app." }
            vm.set("pair.$photoPair.photo", uri.toString()) }
    }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        if(success) vm.set("pair.$photoPair.photo", cameraUri) else photoError = "Photo not captured. Try again or choose a photo."
    }
    LaunchedEffect(Unit) { if(preselectedCustomerId != null && state.fields.isEmpty()) { vm.set("customerId",preselectedCustomerId); vm.set("customerMode","existing"); vm.set("step","1") }; vm.search() }
    val valid = step != 0 || vm.field("customerId").isNotBlank() || (vm.field("customerMode") == "new" && vm.field("name").isNotBlank())
    Scaffold(topBar = { au.mainspring.nativeapp.ui.IntakeHeader("shoe", { leave = true }, !state.busy, { discard = true }, !state.busy && vm.field("uncertain").isBlank() && vm.field("jobId").isBlank(), services, onSwitchService) },
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            if(!state.complete) au.mainspring.nativeapp.ui.WizardBar(step, 4, listOf("Customer", "Pairs and services", "Job details", "Photos")[step],
                if(step == 3) "Create / finish repair" else "Continue",
                { if(step < 3) vm.set("step", "${step + 1}") else vm.submit(context.applicationContext) },
                !state.busy && valid,
                if(step > 0) ({ vm.set("step", "${step - 1}") }) else null, !state.busy)
        }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(listOf("Who is the customer?", "What are we repairing?", "Job details", "Add photos")[step], style = MaterialTheme.typography.titleLarge)
            Text("Your progress is saved on this device as you go.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }; photoError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            vm.field("trackingWarning").takeIf(String::isNotBlank)?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            if(state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            if(vm.field("uncertain").isNotBlank()) OutlinedButton(onClick = { reconcile = true }) { Text("I checked the shop records") }
            if(vm.field("jobId").isNotBlank()) {
                Text("Job saved", style = MaterialTheme.typography.titleLarge)
                state.photoFailures.forEach { au.mainspring.nativeapp.ui.ErrorBanner(it) }
                if(state.complete && state.photoFailures.isEmpty()) Text("Intake complete")
                Button(onClick = { if(state.complete && state.photoFailures.isEmpty()) vm.finish(); onOpenJob(vm.field("jobId")) }, enabled = !state.busy) { Text("Open repair job") }
                if(!state.complete || state.photoFailures.isNotEmpty()) OutlinedButton(onClick = { vm.submit(context.applicationContext) }, enabled = !state.busy) { Text("Finish intake / retry photos") }
            }
            @Composable fun field(key: String, label: String) {
                au.mainspring.nativeapp.ui.AtelierTextField(vm.field(key), { vm.set(key, it) }, label = { Text(label) }, modifier = Modifier.fillMaxWidth(), enabled = !locked)
            }
            if(!state.complete) when(step) {
                0 -> {
                    val new = vm.field("customerMode") == "new"
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        au.mainspring.nativeapp.ui.AtelierChip(selected = !new, onClick = { vm.set("customerMode", "existing") }, enabled = !locked, label = { Text("Existing") })
                        au.mainspring.nativeapp.ui.AtelierChip(selected = new, onClick = { vm.set("customerMode", "new"); vm.set("customerId", "") }, enabled = !locked, label = { Text("New customer") })
                    }
                    if(new) { field("name", "Name *"); field("phone", "Phone"); field("email", "Email") }
                    else {
                        au.mainspring.nativeapp.ui.AtelierTextField(vm.field("query"), { vm.set("query", it) }, label = { Text("Search customers") }, singleLine = true, enabled = !locked, modifier = Modifier.fillMaxWidth(),
                            keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Search),
                            keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSearch = { vm.search() }))
                        state.customers.forEach { c -> au.mainspring.nativeapp.ui.SelectableCard(selected = vm.field("customerId") == c.id, onClick = { vm.set("customerId", c.id); vm.set("accountId", "") }, enabled = !locked) {
                            Text(c.fullName, style = MaterialTheme.typography.titleMedium)
                            c.phone?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) } } }
                    }
                }
                1 -> {
                    Text("Pairs: ${vm.count()}")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = { val n = (vm.count() - 1).coerceAtLeast(1); vm.set("count", "$n"); pair = pair.coerceAtMost(n - 1) }, enabled = !locked && vm.count() > 1) { Text("Remove pair") }
                        OutlinedButton(onClick = { vm.set("count", "${vm.count() + 1}") }, enabled = !locked && vm.count() < 15) { Text("Add pair") }
                    }
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        (0 until vm.count()).forEach { i -> au.mainspring.nativeapp.ui.AtelierChip(selected = pair == i, onClick = { pair = i }, label = { Text("Pair ${i + 1}") }) }
                    }
                    field("pair.$pair.type", "Shoe type"); field("pair.$pair.brand", "Brand"); field("pair.$pair.color", "Colour"); field("pair.$pair.condition", "Condition notes")
                    field("serviceQuery", "Search repair catalogue")
                    val selected = vm.field("pair.$pair.services").split('|').toSet()
                    state.catalogue.filter { it.name.contains(vm.field("serviceQuery"), true) || it.key in selected }.take(40).forEach { item ->
                        au.mainspring.nativeapp.ui.SelectableCard(selected = item.key in selected, onClick = { vm.toggle(pair, item.key) }, enabled = !locked) {
                            Text(item.name, style = MaterialTheme.typography.titleMedium)
                            Text(item.priceCents?.let { formatCents(it, "AUD") } ?: "Inspection quote", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if(item.key in selected) {
                            field("pair.$pair.quantity.${item.key}", "Quantity (default 1)")
                            field("pair.$pair.price.${item.key}", "Agreed unit price ($, optional override)")
                            field("pair.$pair.note.${item.key}", "Service notes")
                        }
                    }
                }
                2 -> {
                    field("title", "Job title (or use selected services)"); field("description", "Instructions / fault description")
                    Text("Initial status")
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on").forEach { value -> au.mainspring.nativeapp.ui.AtelierChip(selected = vm.field("status").ifBlank { "awaiting_go_ahead" } == value, onClick = { vm.set("status", value) }, enabled = !locked, label = { Text(au.mainspring.nativeapp.ui.statusLabel(value)) }) }
                    }
                    Text("Priority")
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("low", "normal", "high", "urgent").forEach { value -> au.mainspring.nativeapp.ui.AtelierChip(selected = vm.field("priority").ifBlank { "normal" } == value, onClick = { vm.set("priority", value) }, enabled = !locked, label = { Text(value.replaceFirstChar { it.uppercase() }) }) }
                    }
                    field("salesperson", "Salesperson"); field("collection", "Collection date (DD/MM/YYYY)"); field("deposit", "Deposit ($, entire job)")
                    val accounts = state.accounts.filter { it.active && (vm.field("customerId").isBlank() || vm.field("customerId") in it.customerIds) }
                    if(accounts.isNotEmpty()) {
                        Text("Customer account")
                        au.mainspring.nativeapp.ui.AtelierChip(selected = vm.field("accountId").isBlank(), onClick = { vm.set("accountId", "") }, enabled = !locked, label = { Text("No account") })
                        accounts.forEach { a -> au.mainspring.nativeapp.ui.AtelierChip(selected = vm.field("accountId") == a.id, onClick = { vm.set("accountId", a.id) }, enabled = !locked, label = { Text(a.name) }) }
                    }
                }
                3 -> {
                    Text("Optional intake photo for each pair")
                    (0 until vm.count()).forEach { i ->
                        val uri = vm.field("pair.$i.photo")
                        Text("Pair ${i + 1}")
                        if(uri.isNotBlank()) PhotoThumbnail(uri, "Pair ${i + 1} intake photo")
                        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { photoPair = i; picker.launch(arrayOf("image/jpeg", "image/png", "image/webp")) }, enabled = !state.busy) { Text("Choose") }
                            OutlinedButton(onClick = {
                                photoPair = i; val directory = File(context.filesDir, "intake-photos").apply { mkdirs() }
                                val file = File.createTempFile("shoe-", ".jpg", directory)
                                val output = FileProvider.getUriForFile(context, "${context.packageName}.intake", file); cameraUri = output.toString()
                                try { camera.launch(output) } catch(_: Exception) { photoError = "Camera unavailable. Choose a photo instead." }
                            }, enabled = !state.busy) { Text("Camera") }
                            if(uri.isNotBlank()) TextButton(onClick = { vm.set("pair.$i.photo", "") }, enabled = !state.busy) { Text("Remove") }
                        }
                    }
                    Text("Creating this repair may send a tracking SMS to the customer.")
                }
            }
        }
    }
    if(leave) AlertDialog(onDismissRequest = { leave = false }, title = { Text("Leave intake?") }, text = { Text("Your draft and pending photos are saved on this device.") },
        confirmButton = { TextButton(onClick = onBack) { Text("Save and leave") } }, dismissButton = { TextButton(onClick = { leave = false }) { Text("Keep editing") } })
    if(discard) AlertDialog(onDismissRequest = { discard = false }, title = { Text("Discard draft?") }, text = { Text("This clears the device draft, not shop records already saved.") },
        confirmButton = { TextButton(onClick = { vm.discard(); discard = false }) { Text("Discard") } }, dismissButton = { TextButton(onClick = { discard = false }) { Text("Cancel") } })
    if(reconcile) AlertDialog(onDismissRequest = { reconcile = false }, title = { Text("No record was saved?") }, text = { Text("Continue only after checking that the last attempted save did not create a customer, shoe, ticket, or added pair/service. Retrying an existing save can duplicate it.") },
        confirmButton = { TextButton(onClick = { vm.set("uncertain", ""); reconcile = false }) { Text("Not saved — allow retry") } }, dismissButton = { TextButton(onClick = { reconcile = false }) { Text("Cancel") } })
}

