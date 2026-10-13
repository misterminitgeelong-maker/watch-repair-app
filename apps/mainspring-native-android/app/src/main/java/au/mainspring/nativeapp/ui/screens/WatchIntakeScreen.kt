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
import au.mainspring.nativeapp.WatchIntakeViewModel
import au.mainspring.nativeapp.ui.formatCents
import au.mainspring.nativeapp.ui.PhotoThumbnail
import java.io.File
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WatchIntakeScreen(onBack: () -> Unit, onOpenJob: (String) -> Unit, vm: WatchIntakeViewModel = viewModel(), preselectedCustomerId: String? = null) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val focus = androidx.compose.ui.platform.LocalFocusManager.current
    val keyboard = androidx.compose.ui.platform.LocalSoftwareKeyboardController.current
    val step = vm.field("step").toIntOrNull()?.coerceIn(0,3) ?: 0
    var activeWatch by rememberSaveable { mutableIntStateOf(0) }
    var photoWatch by rememberSaveable { mutableIntStateOf(0) }
    var photoSide by rememberSaveable { mutableStateOf("front") }
    var cameraUri by rememberSaveable { mutableStateOf("") }
    var closeDialog by remember { mutableStateOf(false) }
    var discardDialog by remember { mutableStateOf(false) }
    var photoError by remember { mutableStateOf<String?>(null) }
    var reconcileDialog by remember { mutableStateOf(false) }
    val newCustomer = vm.field("customerMode") == "new"
    val locked = state.busy || state.savedJobIds.isNotEmpty() || vm.field("uncertainWrite").isNotBlank() || vm.field("hasAcknowledgement") == "true"
    fun close() { if (!state.busy) closeDialog = true }
    BackHandler { close() }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            try { context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            catch (_: SecurityException) { photoError = "This provider cannot retain access after closing the app. Reselect the photo if needed." }
            vm.setPhoto(photoWatch, photoSide, uri.toString())
        }
    }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        if (success && cameraUri.isNotBlank()) vm.setPhoto(photoWatch, photoSide, cameraUri)
        else photoError = "Photo was not captured. Try again or choose a photo."
    }
    LaunchedEffect(Unit) {
        if(preselectedCustomerId != null && state.fields.isEmpty()) { vm.selectCustomer(preselectedCustomerId); vm.setField("step", "1") }
        vm.searchCustomers(vm.field("customerQuery"))
    }
    val valid = when(step) { 0 -> if(newCustomer) vm.field("name").isNotBlank() else vm.field("customerId").isNotBlank(); 2 -> vm.field("title").isNotBlank(); else -> true }
    Scaffold(topBar = { TopAppBar(title = { Text("New watch repair", style = MaterialTheme.typography.titleLarge) }, navigationIcon = {
        au.mainspring.nativeapp.ui.BackButton(onClick = ::close, enabled = !state.busy)
    }, actions = { TextButton(onClick = { discardDialog = true }, enabled = !state.busy && vm.field("uncertainWrite").isBlank() && state.savedJobIds.isEmpty(), modifier = Modifier.heightIn(min = 48.dp)) { Text("Discard") } }) },
        bottomBar = {
            if (!state.complete) au.mainspring.nativeapp.ui.WizardBar(step, 4, listOf("Customer", "Watches", "Job details", "Photos")[step],
                if(step == 3) "Create / finish intake" else "Continue",
                { focus.clearFocus(); keyboard?.hide(); if(step < 3) vm.setField("step", (step + 1).toString()) else vm.submit(context.applicationContext) },
                !state.busy && valid,
                if(step > 0) ({ vm.setField("step", (step - 1).toString()) }) else null, !state.busy)
        }) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(listOf("Who is the customer?", "Which watches are coming in?", "What needs doing?", "Add photos")[step], style = MaterialTheme.typography.titleLarge)
            Text("Your progress is saved on this device as you go.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            state.fields.filterKeys { it.startsWith("warning.") }.values.forEach { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            if (vm.field("uncertainWrite").isNotBlank()) {
                Text("The last save has an unknown result. Check your shop's customer/job records before saving again.")
                OutlinedButton(onClick = { reconcileDialog = true }) { Text("I checked the records") }
            }
            photoError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            state.progress?.let { Text(it); LinearProgressIndicator(Modifier.fillMaxWidth()) }
            if(vm.field("hasAcknowledgement") == "true" && state.savedJobIds.isEmpty()) Text("Some intake records are already saved. Continue this intake, or discard the device draft and use the saved records in a new intake.")
            if (state.savedJobIds.isNotEmpty()) {
                Text("${state.savedJobIds.size} of ${vm.count()} tickets saved", style = MaterialTheme.typography.headlineSmall)
                state.uploadFailures.forEach { au.mainspring.nativeapp.ui.ErrorBanner(it) }
                if (state.complete && state.uploadFailures.isEmpty()) Text("Intake complete")
                if (!state.busy && (!state.complete || state.uploadFailures.isNotEmpty())) Button(onClick = { vm.submit(context.applicationContext) }) { Text("Continue / retry remaining photos") }
                state.savedJobIds.forEachIndexed { index, id ->
                    Button(onClick = {
                        if (state.complete && state.uploadFailures.isEmpty()) vm.finish()
                        onOpenJob(id)
                    }, enabled = !state.busy) { Text("Open Watch ${index + 1} job") }
                }
            }
            @Composable fun field(key: String, label: String, multiline: Boolean = false) {
                OutlinedTextField(value = vm.field(key), onValueChange = { vm.setField(key, it) }, label = { Text(label) },
                    keyboardOptions = KeyboardOptions(keyboardType = when(key) { "deposit", "preQuote" -> KeyboardType.Decimal; "phone" -> KeyboardType.Phone; "email" -> KeyboardType.Email; else -> KeyboardType.Text }),
                    singleLine = !multiline, enabled = !locked, modifier = Modifier.fillMaxWidth())
            }
            if (!state.complete) when(step) {
                0 -> {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(selected = !newCustomer, onClick = { vm.setField("customerMode", "existing") }, enabled = !locked, label = { Text("Existing") })
                        FilterChip(selected = newCustomer, onClick = { vm.setField("customerMode", "new"); vm.selectCustomer("") }, enabled = !locked, label = { Text("New customer") })
                    }
                    if (newCustomer) {
                        field("name", "Customer name *"); field("phone", "Phone"); field("email", "Email")
                        field("address", "Address", true); field("customerNotes", "Customer notes", true)
                    } else {
                        OutlinedTextField(value = vm.field("customerQuery"), onValueChange = { vm.setField("customerQuery", it); vm.searchCustomers(it) }, label = { Text("Search name, phone or email") },
                            singleLine = true, enabled = !locked, modifier = Modifier.fillMaxWidth(),
                            keyboardOptions = KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Search),
                            keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSearch = { vm.searchCustomers(vm.field("customerQuery")); keyboard?.hide() }))
                        if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                        state.customers.forEach { customer ->
                            au.mainspring.nativeapp.ui.SelectableCard(selected = vm.field("customerId") == customer.id, onClick = { vm.selectCustomer(customer.id) }, enabled = !locked) {
                                Text(customer.fullName, style = MaterialTheme.typography.titleMedium)
                                listOfNotNull(customer.phone, customer.email).takeIf { it.isNotEmpty() }?.let { Text(it.joinToString(" · "), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                            }
                        }
                        if (!state.loading && state.customers.isEmpty()) Text("No matching customers. Try another search or choose New customer.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                1 -> {
                    Text("Number of watches")
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        (1..5).forEach { n -> FilterChip(selected = vm.count() == n, onClick = { vm.changeCount(n); activeWatch = activeWatch.coerceAtMost(n - 1) }, enabled = !locked, label = { Text("$n") }) }
                    }
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        (0 until vm.count()).forEach { i -> FilterChip(selected = activeWatch == i, onClick = { activeWatch = i }, label = { Text("Watch ${i + 1}") }) }
                    }
                    val prefix = "watch.$activeWatch"
                    au.mainspring.nativeapp.ui.SelectableCard(selected = vm.field("$prefix.id").isBlank(), onClick = { vm.setField("$prefix.id", "") }, enabled = !locked) { Text("New watch", style = MaterialTheme.typography.titleMedium); Text("Enter its details below", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    if (!newCustomer) state.watches.forEach { watch ->
                        au.mainspring.nativeapp.ui.SelectableCard(selected = vm.field("$prefix.id") == watch.id, onClick = { vm.setField("$prefix.id", watch.id) }, enabled = !locked) {
                            Text(listOfNotNull(watch.brand, watch.model).joinToString(" ").ifBlank { "Existing watch" }, style = MaterialTheme.typography.titleMedium)
                            watch.serialNumber?.takeIf { it.isNotBlank() }?.let { Text("Serial $it", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                    }
                    if (vm.field("$prefix.id").isBlank()) {
                        field("$prefix.brand", "Brand"); field("$prefix.model", "Model"); field("$prefix.serial", "Serial number")
                        field("$prefix.movement", "Movement type"); field("$prefix.condition", "Condition at intake", true)
                    }
                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Checkbox(checked = vm.field("quickJob") == "true", onCheckedChange = { vm.setField("quickJob", it.toString()) }, enabled = !locked)
                        Text("Quick counter job (photos optional)")
                    }
                }
                2 -> {
                    field("serviceQuery", "Search repair catalogue")
                    val query = vm.field("serviceQuery")
                    state.catalogue.filter { it.name.contains(query, true) || it.groupLabel.orEmpty().contains(query, true) }.take(30).forEach { item ->
                        au.mainspring.nativeapp.ui.SelectableCard(selected = item.key in vm.selectedServices(), onClick = { vm.toggleService(item.key) }, enabled = !locked) {
                            Text(item.name, style = MaterialTheme.typography.titleMedium)
                            Text(item.priceCents?.let { formatCents(it, "AUD") } ?: "Quote required", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    field("title", "Job title *"); field("description", "Instructions / fault description", true)
                    val quoteRequired = state.catalogue.any { it.key in vm.selectedServices() && it.pricingType == "quote" }
                    Text("Initial status")
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on").forEach { status ->
                            FilterChip(selected = vm.field("status").ifBlank { "awaiting_quote" } == status, onClick = { vm.setField("status", status) }, enabled = !locked && !quoteRequired,
                                label = { Text(au.mainspring.nativeapp.ui.statusLabel(status)) })
                        }
                    }
                    Text("Priority")
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("low", "normal", "high", "urgent").forEach { priority ->
                            FilterChip(selected = vm.field("priority").ifBlank { "normal" } == priority, onClick = { vm.setField("priority", priority) }, enabled = !locked, label = { Text(priority.replaceFirstChar { it.uppercase() }) })
                        }
                    }
                    field("salesperson", "Salesperson"); field("collection", "Collection date (DD/MM/YYYY)")
                    field("deposit", "Deposit ($)"); field("preQuote", "Pre-quote ($)")
                    if (vm.count() > 1) Text("Deposit and pre-quote apply to each ticket, matching the web intake.")
                    if(vm.count() == 1) field("ticketOverride", "Ticket number override (optional)")
                    val accounts = state.accounts.filter { it.active && (vm.field("customerId").isBlank() || vm.field("customerId") in it.customerIds) }
                    if(accounts.isNotEmpty()) {
                        Text("Bill to customer account")
                        FilterChip(selected = vm.field("accountId").isBlank(), onClick = { vm.setField("accountId", "") }, enabled = !locked, label = { Text("No account") })
                        accounts.forEach { account -> FilterChip(selected = vm.field("accountId") == account.id, onClick = { vm.setField("accountId", account.id) }, enabled = !locked, label = { Text(account.name) }) }
                    }
                }
                3 -> {
                    Text("Front and back photos per watch. JPEG, PNG or WebP, up to 10 MB each.")
                    (0 until vm.count()).forEach { i ->
                        Text("Watch ${i + 1}", style = MaterialTheme.typography.titleMedium)
                        listOf("front", "back").forEach { side ->
                            Text(side.replaceFirstChar(Char::uppercase) + if(vm.photo(i, side).isNotBlank()) " · attached" else " · no photo")
                            if(vm.photo(i, side).isNotBlank()) PhotoThumbnail(vm.photo(i, side), "Watch ${i + 1} $side intake photo")
                            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedButton(onClick = {
                                    photoWatch = i; photoSide = side
                                    val directory = File(context.filesDir, "intake-photos").apply { mkdirs() }
                                    val file = File.createTempFile("watch-", ".jpg", directory)
                                    val uri = FileProvider.getUriForFile(context, "${context.packageName}.intake", file)
                                    cameraUri = uri.toString()
                                    try { camera.launch(uri) } catch (_: Exception) { photoError = "Camera unavailable. Choose a photo instead." }
                                }, enabled = !state.busy) { Text("Camera") }
                                OutlinedButton(onClick = { photoWatch = i; photoSide = side; picker.launch(arrayOf("image/jpeg", "image/png", "image/webp")) }, enabled = !state.busy) { Text("Choose") }
                                if(vm.photo(i, side).isNotBlank()) TextButton(onClick = { vm.setPhoto(i, side, "") }, enabled = !state.busy) { Text("Remove") }
                            }
                        }
                    }
                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        Checkbox(checked = vm.field("skipPhotos") == "true", onCheckedChange = { vm.setField("skipPhotos", it.toString()) }, enabled = !state.busy)
                        Text("Continue without photos")
                    }
                    Text("Creation may send the customer's tracking SMS.")
                }
            }
        }
    }
    if(closeDialog) AlertDialog(onDismissRequest = { closeDialog = false }, title = { Text("Leave intake?") },
        text = { Text("Your draft and pending photos stay on this device for your next visit.") },
        confirmButton = { TextButton(onClick = { closeDialog = false; onBack() }) { Text("Save and leave") } },
        dismissButton = { TextButton(onClick = { closeDialog = false }) { Text("Keep editing") } })
    if(discardDialog) AlertDialog(onDismissRequest = { discardDialog = false }, title = { Text("Discard this draft?") },
        text = { Text("This clears intake details on this device. It does not delete records already saved to your shop.") },
        confirmButton = { TextButton(onClick = { vm.clearDraft(); discardDialog = false }) { Text("Discard") } },
        dismissButton = { TextButton(onClick = { discardDialog = false }) { Text("Cancel") } })
    if(reconcileDialog) AlertDialog(onDismissRequest = { reconcileDialog = false }, title = { Text("Confirm no record was saved") },
        text = { Text("Continue only if you checked the shop records and the last attempted customer, watch or job was not saved. If it exists, use that record instead; repeating this save can create a duplicate.") },
        confirmButton = { TextButton(onClick = { vm.confirmNoUnknownRecord(); reconcileDialog = false }) { Text("Not saved — allow retry") } },
        dismissButton = { TextButton(onClick = { reconcileDialog = false }) { Text("Cancel") } })
}
