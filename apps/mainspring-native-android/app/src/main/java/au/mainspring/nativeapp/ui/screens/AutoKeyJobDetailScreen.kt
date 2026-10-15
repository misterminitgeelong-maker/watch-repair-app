package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.ui.*
import au.mainspring.nativeapp.api.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun AutoKeyJobDetailScreen(
    jobId: String, apiBaseUrl: String, onBack: () -> Unit, onMessages: () -> Unit,
    onFinance: (Boolean) -> Unit, onEdit: () -> Unit, onPhotos: () -> Unit = {}, onArrival: () -> Unit = {},
    onSignature: (String) -> Unit = {}, initialStatus: String? = null, embedded: Boolean = false, onOpenJob: ((String) -> Unit)? = null,
    vm: AutoKeyJobDetailViewModel = viewModel(key = "$jobId|$apiBaseUrl", factory = AutoKeyJobDetailViewModel.factory(jobId,apiBaseUrl)),
) {
    val state by vm.state.collectAsStateWithLifecycle()
    val financeModel: MobileFinanceViewModel = viewModel(key=jobId,factory=MobileFinanceViewModel.factory(jobId))
    val financialState by financeModel.state.collectAsStateWithLifecycle()
    RefreshOnResume(vm::load)
    val context = LocalContext.current
    val compactHeader=androidx.compose.ui.platform.LocalConfiguration.current.screenHeightDp<540
    val j = state.job
    val paymentRecorded=financialState.invoices.isNotEmpty() && financialState.invoices.all {it.status=="paid"} && financialState.error==null
    val journey=j?.let {
        val stage=fieldJourney(it.status)
        when {
            paymentRecorded && stage.step>=3 -> fieldJourney("invoice_paid")
            stage.step==2 && financialState.quotes.any {quote->quote.status=="approved"} && financialState.error==null -> FieldJourney(2,"Quote approved","Finish the agreed work, then review the invoice.","Finish work","work_completed")
            else -> stage
        }
    }
    var suggestedStatus by rememberSaveable(jobId) {mutableStateOf(initialStatus?.takeIf {it=="en_route"})}
    var confirmEnRoute by rememberSaveable(jobId) {mutableStateOf(false)}
    LaunchedEffect(j?.id,state.loading,state.statusReviewRequired) {if(j!=null && !state.loading && !state.statusReviewRequired && suggestedStatus!=null) {confirmEnRoute=j.status in setOf("booked","booking_confirmed");suggestedStatus=null}}
    var tab by rememberSaveable(jobId) { mutableStateOf("info") }
    val haptics=androidx.compose.ui.platform.LocalHapticFeedback.current
    var lastSeenStatus by remember(jobId) {mutableStateOf<String?>(null)}
    LaunchedEffect(j?.status) {
        if(lastSeenStatus!=null && j?.status!=lastSeenStatus && !state.offlineSnapshot) haptics.performHapticFeedback(androidx.compose.ui.hapticfeedback.HapticFeedbackType.LongPress)
        lastSeenStatus=j?.status
    }
    var confirmDuplicate by rememberSaveable(jobId) {mutableStateOf(false)}
    var confirmDelete by rememberSaveable(jobId) {mutableStateOf(false)}
    var keyLookup by rememberSaveable(jobId) {mutableStateOf(false)}
    LaunchedEffect(tab,state.offlineSnapshot) {if(tab=="activity" && !state.activityLoaded && !state.offlineSnapshot) vm.loadActivity()}
    LaunchedEffect(state.deleted) {if(state.deleted) onBack()}
    var moreActions by rememberSaveable(jobId) {mutableStateOf(false)}
    var statusPicker by remember(jobId) { mutableStateOf(false) }
    var pendingStep by rememberSaveable(jobId) { mutableStateOf<String?>(null) }
    var finishing by rememberSaveable(jobId) { mutableStateOf(false) }
    LaunchedEffect(j?.status,state.statusBusy) {
        if(finishing && j?.status=="work_completed" && !state.statusBusy) { finishing=false;tab="finance" }
        if(finishing && !state.statusBusy && state.error!=null) finishing=false
    }
    var statusChangeNote by rememberSaveable(jobId) { mutableStateOf("") }
    var attachmentOpenError by remember(jobId) { mutableStateOf<String?>(null) }
    fun open(uri: Uri, dial: Boolean = false) {
        try { context.startActivity(Intent(if(dial) Intent.ACTION_DIAL else Intent.ACTION_VIEW,uri)) }
        catch(_: android.content.ActivityNotFoundException) { attachmentOpenError = "No compatible app is available on this device." }
    }
    Scaffold(containerColor=MaterialTheme.colorScheme.background,contentWindowInsets=if(embedded) WindowInsets(0,0,0,0) else ScaffoldDefaults.contentWindowInsets,topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(windowInsets=if(embedded) WindowInsets(0,0,0,0) else TopAppBarDefaults.windowInsets,title = {Column {
            Text(j?.title ?: "Job",style=if(compactHeader) MaterialTheme.typography.titleMedium else MaterialTheme.typography.headlineMedium,maxLines=2,overflow=androidx.compose.ui.text.style.TextOverflow.Ellipsis)
            if(!compactHeader) j?.jobNumber?.let {Text(it,style=MaterialTheme.typography.bodyMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)}
        }},navigationIcon={au.mainspring.nativeapp.ui.BackButton(onBack)},
        actions={TextButton(vm::load,enabled=!state.loading && !state.statusBusy,modifier=Modifier.heightIn(min=48.dp)) { Text("Refresh") };TextButton(onEdit,enabled=!state.loading && !state.statusBusy && !state.offlineSnapshot) {Text("Edit")}}) },
        bottomBar = {
            if(j!=null && tab in listOf("info","vehicle")) {
                val activeJourney=journey ?: fieldJourney(j.status)
                Surface(color=MaterialTheme.colorScheme.surface,shadowElevation=1.dp) {
                    Column(Modifier.fillMaxWidth().then(if(embedded) Modifier else Modifier.navigationBarsPadding()).padding(horizontal=16.dp,vertical=10.dp),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                        if(!compactHeader) Text(activeJourney.title,style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
                        Button({ if(activeJourney.targetStatus!=null) pendingStep=activeJourney.targetStatus else tab="finance" },
                            modifier=Modifier.fillMaxWidth().heightIn(min=52.dp).testTag("job-next-action"),
                            enabled=!state.loading && !state.statusBusy && !state.statusReviewRequired && !state.offlineSnapshot && TokenStore.canWorkJobs()) {
                            Text(if(state.statusBusy) "Saving…" else activeJourney.action)
                        }
                        if(!compactHeader && activeJourney.step==2 && activeJourney.targetStatus!="work_completed") TextButton({pendingStep="work_completed"},enabled=!state.loading && !state.statusBusy && !state.statusReviewRequired && !state.offlineSnapshot && TokenStore.canWorkJobs(),modifier=Modifier.fillMaxWidth()) {Text("Finish work")}
                        if(!compactHeader && activeJourney.targetStatus=="work_completed") TextButton({tab="finance"},modifier=Modifier.fillMaxWidth()) {Text("Review approved quote")}
                    }
                }
            }
        }) {padding ->
        when {
            state.loading && j==null -> CircularProgressIndicator(Modifier.padding(padding).padding(24.dp))
            j==null -> Column(Modifier.padding(padding).padding(16.dp)) {Text(state.error ?: "Job unavailable",color=MaterialTheme.colorScheme.error);OutlinedButton(vm::load) {Text("Retry")}}
            else -> Column(Modifier.fillMaxSize().padding(padding)) {
                if(state.offlineSnapshot) Surface(color=MaterialTheme.colorScheme.secondaryContainer) {
                    Row(Modifier.fillMaxWidth().padding(horizontal=16.dp),verticalAlignment=Alignment.CenterVertically) {
                        Text("Saved copy · reconnect to update",Modifier.weight(1f),style=MaterialTheme.typography.bodySmall)
                        TextButton(vm::load,enabled=!state.loading) {Text("Retry")}
                    }
                }
                Column(Modifier.padding(horizontal=16.dp,vertical=if(compactHeader) 0.dp else 8.dp),verticalArrangement=Arrangement.spacedBy(if(compactHeader) 0.dp else 6.dp)) {
                    if(!compactHeader) Text(listOf(listOfNotNull(j.vehicleMake,j.vehicleModel,j.vehicleYear?.toString()).joinToString(" "),j.customerName.orEmpty()).filter {it.isNotBlank()}.joinToString(" · "),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically) {
                        if(LocalCalibre.current) StatusPill(if(paymentRecorded && fieldJourney(j.status).step>=3) "paid" else j.status)
                        else Surface(color=MaterialTheme.colorScheme.secondary,contentColor=MaterialTheme.colorScheme.onSecondary,shape=MaterialTheme.shapes.small) {
                            Text(statusLabel(if(paymentRecorded && fieldJourney(j.status).step>=3) "paid" else j.status),Modifier.padding(horizontal=16.dp,vertical=12.dp),style=MaterialTheme.typography.titleSmall)
                        }
                        Row {
                            if(!j.customerPhone.isNullOrBlank()) OutlinedButton({open(Uri.fromParts("tel",j.customerPhone,null),true)},Modifier.heightIn(min=48.dp)) {Text("Call")}
                            Spacer(Modifier.width(8.dp))
                            if(!j.jobAddress.isNullOrBlank()) OutlinedButton({open(Uri.parse("geo:0,0?q=${Uri.encode(j.jobAddress)}"))},Modifier.heightIn(min=48.dp)) {Text("Navigate")}
                        }
                    }
                    if(!compactHeader) JourneyProgress((journey ?: fieldJourney(j.status)).step)
                }
                val sections=listOf("info" to "Info","vehicle" to "Vehicle & Key","finance" to "Financial","photos" to "Photos","messages" to "Messages","activity" to "Activity")
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal=16.dp,vertical=6.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    sections.forEach {(key,label)->PillChip(label,tab==key,{tab=key})}
                }
                AnimatedContent(targetState=tab,modifier=Modifier.weight(1f).testTag("job-detail-body"),label="job-section") { activeTab ->
                    if(state.offlineSnapshot && activeTab in listOf("finance","photos","messages","activity")) Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
                        Text("Reconnect to load current ${when(activeTab) {"finance"->"quotes, invoices and payments";"activity"->"the activity log";else->activeTab}}.")
                        OutlinedButton(vm::load,enabled=!state.loading) {Text("Retry connection")}
                    } else when(activeTab) {
                        "finance" -> MobileFinanceScreen(jobId,{tab="info"},businessAccount=j.customerAccountId!=null,onSignature=onSignature,embedded=true)
                        "photos" -> JobPhotosScreen("auto-key-jobs",jobId,{tab="info"},embedded=true)
                        "messages" -> MessageThreadScreen("auto-key-jobs",jobId,{tab="info"},embedded=true)
                        "activity" -> JobActivityList(state.activity,state.activityLoading,state.activityError,onRetry=vm::loadActivity)
                        else -> LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
                            item {
                                if(state.loading || state.statusBusy) LinearProgressIndicator(Modifier.fillMaxWidth())
                                au.mainspring.nativeapp.ui.PendingStatusBanner(jobId)
                                au.mainspring.nativeapp.ui.SyncedRefreshEffect(jobId) { vm.load() }
                                state.error?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)}
                                state.statusInfo?.let {Text(it)}
                                attachmentOpenError?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)}
                                if(state.statusReviewRequired) FlatPanel {
                                    Text("Review the current job status before repeating the last change.")
                                    state.requestedStatus?.let {Text("Previously requested: ${it.replace('_',' ')}")}
                                    state.requestedNote?.let {Text("Previous note: $it")}
                                    OutlinedButton(vm::reviewedStatus,enabled=!state.loading && !state.statusBusy && state.historyChecked) {Text("I have reviewed the current status")}
                                }
                                if(activeTab=="vehicle") {
                                    SectionLabel("Vehicle")
                                    FlatPanel {DetailRow("Make / model",listOfNotNull(j.vehicleMake,j.vehicleModel).joinToString(" "));DetailRow("Year",j.vehicleYear?.toString().orEmpty());DetailRow("Registration",j.registrationPlate.orEmpty());DetailRow("VIN",j.vin.orEmpty())}
                                    SectionLabel("Key details")
                                    FlatPanel {DetailRow("Key type",j.keyType.orEmpty());DetailRow("Blade",j.bladeCode.orEmpty());DetailRow("Transponder",j.chipType.orEmpty());DetailRow("Keys to make",j.keyQuantity.toString());DetailRow("Programming",au.mainspring.nativeapp.ui.statusLabel(j.programmingStatus))}
                                    state.vehicleContext?.let {knowledge ->
                                        contextText(knowledge,"complexity")?.let {DetailRow("AKL complexity",it)}
                                        knowledge.getAsJsonArray("known_issues")?.takeIf {it.size()>0}?.let {issues ->
                                            SectionLabel("Known issues")
                                            issues.forEach {entry->FlatPanel {
                                                val issue=entry.asJsonObject
                                                contextText(issue,"issue")?.let {Text(it,style=MaterialTheme.typography.titleSmall,color=MaterialTheme.colorScheme.primary)}
                                                contextText(issue,"severity")?.let {Text(it,style=MaterialTheme.typography.labelSmall)}
                                                contextText(issue,"notes")?.let {Text(it,style=MaterialTheme.typography.bodySmall)}
                                                contextText(issue,"resolution")?.let {Text("Resolution: $it",style=MaterialTheme.typography.bodySmall)}
                                            } }
                                        }
                                        knowledge.getAsJsonArray("tool_recommendations")?.takeIf {it.size()>0}?.let {tools ->
                                            SectionLabel("Recommended tools")
                                            tools.forEach {entry->FlatPanel {
                                                val tool=entry.asJsonObject
                                                listOf("primary_tool" to "Primary","backup_tool" to "Backup","escalation_tool" to "Escalation").forEach {(key,label)->contextText(tool,key)?.let {DetailRow(label,it)}}
                                                contextText(tool,"notes")?.let {Text(it,style=MaterialTheme.typography.bodySmall)}
                                            } }
                                        }
                                        knowledge.getAsJsonArray("cutting_profiles")?.takeIf {it.size()>0}?.let {profiles ->
                                            SectionLabel("Cutting profiles")
                                            profiles.forEach {entry->FlatPanel {
                                                val profile=entry.asJsonObject
                                                listOf("blank_reference" to "Blank","description" to "Description","dolphin_xp005l" to "Dolphin XP005L","condor_xc_mini_plus_ii" to "Condor XC Mini Plus II","silca_alpha_pro" to "Silca Alpha Pro","silca_futura_pro" to "Silca Futura Pro").forEach {(key,label)->contextText(profile,key)?.let {DetailRow(label,it)}}
                                            } }
                                        }
                                    }
                                    state.keySearchError?.takeIf {!keyLookup}?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)}
                                    OutlinedButton({vm.clearKeySearch();keyLookup=true},modifier=Modifier.fillMaxWidth().testTag("job-key-lookup"),enabled=!state.offlineSnapshot && !state.loading && !state.statusBusy && TokenStore.canWorkJobs()) {Text("Look up key details")}
                                    TextButton(onEdit,enabled=!state.offlineSnapshot) {Text("Edit vehicle and key details")}
                                } else {
                                    val activeJourney=journey ?: fieldJourney(j.status)
                                    if(activeJourney.step in 0..2) {
                                        PreparationPanel(j,state.vehicleContext,onVehicle={tab="vehicle"})
                                    }
                                    MobileInfoPanels(j,state.technicians)
                                }
                                TextButton({moreActions=!moreActions},colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.onSurfaceVariant)) {Text(if(moreActions) "Hide job actions" else "More job actions")}
                                if(moreActions) Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
                                    TextButton(onArrival,enabled=TokenStore.canWorkJobs() && !state.statusBusy && !state.offlineSnapshot) {Text("Arrival message")}
                                    state.adminError?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)}
                                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                                        OutlinedButton({confirmDuplicate=true},modifier=Modifier.weight(1f).testTag("job-duplicate"),enabled=TokenStore.canWorkJobs() && !state.adminBusy && !state.statusBusy && !state.offlineSnapshot) {Text("Duplicate job")}
                                        if(TokenStore.canManageInvoices()) OutlinedButton({confirmDelete=true},modifier=Modifier.weight(1f).testTag("job-delete"),enabled=!state.adminBusy && !state.statusBusy && !state.offlineSnapshot) {Text("Delete job",color=MaterialTheme.colorScheme.error)}
                                    }
                                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                                    OutlinedButton({tab="finance"},modifier=Modifier.weight(1f)) {Text("Quote / invoice")}
                                    OutlinedButton({statusChangeNote="";statusPicker=true},modifier=Modifier.weight(1f),
                                        enabled=!state.loading && !state.statusBusy && !state.statusReviewRequired && !state.offlineSnapshot && TokenStore.canWorkJobs()) {Text(if(state.statusBusy) "Updating…" else "Change status")}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    pendingStep?.let {target ->
        val completion=target=="work_completed"
        AlertDialog(onDismissRequest={if(!state.statusBusy) pendingStep=null},
            title={Text(when(target) {"en_route"->"Ready to leave?";"on_site"->"Arrived at the job?";else->"Finish this job?"})},
            text={Column(verticalArrangement=Arrangement.spacedBy(12.dp)) {
                Text(if(completion) "Confirm the work is finished. This can create an invoice and notify the customer through your shop settings. Payment is recorded separately." else "Update the job to ${target.replace('_',' ')}. Customer notifications follow your shop settings.")
                if(completion) au.mainspring.nativeapp.ui.AtelierTextField(statusChangeNote,{statusChangeNote=it},label={Text("Completion note (optional)")},modifier=Modifier.fillMaxWidth(),maxLines=3)
            }},
            confirmButton={Button({pendingStep=null;finishing=completion;vm.setStatus(target,if(completion) statusChangeNote.trim().takeIf {it.isNotEmpty()} else null);statusChangeNote=""},
                enabled=!state.loading && !state.statusBusy && !state.statusReviewRequired && !state.offlineSnapshot && TokenStore.canWorkJobs()) {Text(if(completion) "Confirm completion" else "Confirm ${target.replace('_',' ')}")}},
            dismissButton={TextButton({pendingStep=null}) {Text("Cancel")}})
    }

    if(confirmEnRoute) AlertDialog(onDismissRequest={confirmEnRoute=false},title={Text("Mark En Route")},text={Text("Update this job to En Route. Customer notifications follow your shop settings.")},
        confirmButton={Button({confirmEnRoute=false;vm.setStatus("en_route")},enabled=!state.loading && !state.statusBusy && !state.statusReviewRequired && !state.offlineSnapshot && TokenStore.canWorkJobs()) {Text("Confirm En Route")}},dismissButton={TextButton({confirmEnRoute=false}) {Text("Cancel")}})

    if(confirmDuplicate) AlertDialog(onDismissRequest={confirmDuplicate=false},title={Text("Duplicate this job?")},
        text={Text("Creates a new job with the same customer, vehicle and key details. The original is not changed.")},
        confirmButton={Button({confirmDuplicate=false;vm.duplicate()}) {Text("Duplicate")}},dismissButton={TextButton({confirmDuplicate=false}) {Text("Cancel")}})
    state.duplicated?.let {copy -> AlertDialog(onDismissRequest=vm::dismissAdminMessage,title={Text("Job duplicated")},
        text={Text("Created ${copy.jobNumber}.${if(onOpenJob==null) " Find it in the job list." else ""}")},
        confirmButton={if(onOpenJob!=null) Button({vm.dismissAdminMessage();onOpenJob(copy.id)}) {Text("Open duplicate")} else TextButton(vm::dismissAdminMessage) {Text("Done")}},
        dismissButton={if(onOpenJob!=null) TextButton(vm::dismissAdminMessage) {Text("Stay here")}}) }
    if(confirmDelete) AlertDialog(onDismissRequest={confirmDelete=false},title={Text("Delete this job?")},
        text={Text("This permanently removes ${j?.jobNumber.orEmpty()} with its quotes and photos. This cannot be undone.")},
        confirmButton={Button({confirmDelete=false;vm.deleteJob()}) {Text("Delete job")}},dismissButton={TextButton({confirmDelete=false}) {Text("Cancel")}})
    if(keyLookup && j!=null) KeyLookupDialog(j,state,onSearch=vm::searchKeys,onApply=vm::applyKeyMatch,onClose={keyLookup=false})

    if (statusPicker) {
        AlertDialog(
            onDismissRequest = { statusPicker = false },
            title = { Text("Choose status") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    Text("Completing work can create an invoice and notify the customer. Review the job before choosing a completion status.")
                    au.mainspring.nativeapp.ui.AtelierTextField(
                        value = statusChangeNote,
                        onValueChange = { statusChangeNote = it },
                        label = { Text("Note (optional)") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = false,
                        maxLines = 3,
                    )
                    val currentStage = canonicalMobileStatus(j?.status.orEmpty())
                    MOBILE_STATUS_PICKER.forEach { (key, label) ->
                        TextButton(onClick = {
                            vm.setStatus(key, statusChangeNote.trim().takeIf { it.isNotEmpty() })
                            statusChangeNote = ""
                            statusPicker = false
                        }, modifier = Modifier.fillMaxWidth()) {
                            Column(Modifier.fillMaxWidth()) {
                                Text(if(key == currentStage) "$label (current)" else label, fontWeight = if(key == currentStage) FontWeight.Bold else FontWeight.Normal)
                                Text(key, style = Calibre.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { statusPicker = false }) { Text("Close") }
            },
        )
    }
}


private fun contextText(value: com.google.gson.JsonObject,key: String): String? = value.get(key)?.takeIf {it.isJsonPrimitive}?.asString?.takeIf {it.isNotBlank()}

@Composable private fun MobileInfoPanels(job: au.mainspring.nativeapp.api.AutoKeyJobRead,technicians: List<au.mainspring.nativeapp.api.TeamUser>) {
    var details by rememberSaveable(job.id) {mutableStateOf(false)}
    Column(Modifier.fillMaxWidth(),verticalArrangement=Arrangement.spacedBy(8.dp)) {
        au.mainspring.nativeapp.ui.CustomFieldsCard(au.mainspring.nativeapp.CustomFieldJobKind.Mobile, job.id)
        job.description?.takeIf {it.isNotBlank()}?.let {SectionLabel("Requested work");Surface(Modifier.fillMaxWidth(),shape=MaterialTheme.shapes.medium,color=MaterialTheme.colorScheme.surface) {Text(it,Modifier.padding(horizontal=16.dp,vertical=14.dp),style=MaterialTheme.typography.bodyMedium)}}
        job.techNotes?.takeIf {it.isNotBlank()}?.let {SectionLabel("Tech notes");Surface(Modifier.fillMaxWidth(),shape=MaterialTheme.shapes.medium,color=MaterialTheme.colorScheme.surface) {Text(it,Modifier.padding(horizontal=16.dp,vertical=14.dp),style=MaterialTheme.typography.bodyMedium)}}
        if(job.description.isNullOrBlank() && job.techNotes.isNullOrBlank()) Text("No job notes recorded",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        FlatPanel {
            listOfNotNull(job.customerName,job.customerPhone).takeIf {it.isNotEmpty()}?.let {DetailRow("Customer",it.joinToString(" · "))}
            DetailRow("When",job.scheduledAt?.let {formatShopDate(it,TokenStore.calendarTimezone())} ?: "Unscheduled")
            DetailRow("Where",job.jobAddress.orEmpty())
        }
        TextButton({details=!details},modifier=Modifier.fillMaxWidth(),colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.onSurface)) {
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically) {
                Text(if(details) "Hide customer & booking details" else "Customer & booking details",Modifier.weight(1f),style=MaterialTheme.typography.labelLarge)
                Text(if(details) "−" else "+",Modifier.padding(start=8.dp),style=MaterialTheme.typography.titleMedium)
            }
        }
        if(details) FlatPanel {
            DetailRow("Customer",job.customerName.orEmpty());DetailRow("Mobile",job.customerPhone.orEmpty())
            DetailRow("Account",if(job.customerAccountId!=null) "Business account linked" else "Personal customer")
            DetailRow("Type",job.jobType ?: job.title);DetailRow("Priority",job.priority.orEmpty())
            DetailRow("Technician",technicians.firstOrNull {it.id==job.assignedUserId}?.name ?: if(job.assignedUserId==null) "Unassigned" else "Assigned")
            DetailRow("Scheduled",job.scheduledAt?.let {formatShopDate(it,TokenStore.calendarTimezone())} ?: "Unscheduled")
            DetailRow("Address",job.jobAddress.orEmpty());DetailRow("Created",formatShopDate(job.createdAt))
        }
    }
}


@Composable private fun JourneyProgress(current: Int) {
    if(current<0) return
    Row(Modifier.fillMaxWidth().padding(vertical=4.dp),horizontalArrangement=Arrangement.spacedBy(4.dp)) {
        listOf("Booked","Travel","On site","Done","Paid").forEachIndexed {index,label ->
            Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                Box(Modifier.fillMaxWidth().height(3.dp).background(if(index<=current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,RoundedCornerShape(2.dp)))
                Text(label,style=MaterialTheme.typography.labelSmall,fontWeight=if(index==current) FontWeight.Bold else FontWeight.Normal,color=if(index==current) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
@Composable private fun PreparationPanel(job: au.mainspring.nativeapp.api.AutoKeyJobRead,knowledge: com.google.gson.JsonObject?,onVehicle: () -> Unit) {
    Surface(Modifier.fillMaxWidth(),shape=MaterialTheme.shapes.medium,color=MaterialTheme.colorScheme.surface) {
        Column(Modifier.padding(horizontal=16.dp,vertical=14.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
            Text("APPOINTMENT",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            Text(job.jobAddress?.takeIf {it.isNotBlank()} ?: "Address not recorded",modifier=Modifier.testTag("job-preparation-address"),style=MaterialTheme.typography.titleSmall,fontWeight=FontWeight.SemiBold)
            Text(job.scheduledAt?.let {formatShopDate(it,TokenStore.calendarTimezone())} ?: "Booking time not recorded",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
            val issues=knowledge?.getAsJsonArray("known_issues")?.size() ?: 0
            val tools=knowledge?.getAsJsonArray("tool_recommendations")?.size() ?: 0
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(3.dp)) {
                    Text(listOfNotNull(job.keyType?.takeIf {it.isNotBlank()},job.bladeCode?.takeIf {it.isNotBlank()},job.chipType?.takeIf {it.isNotBlank()}).joinToString(" · ").ifBlank {"Check key specification"},style=MaterialTheme.typography.bodySmall,fontWeight=FontWeight.SemiBold)
                    Text(when {issues>0 -> "$issues known vehicle issue${if(issues==1) "" else "s"} to review";tools>0 -> "Equipment recommendations available";else -> "Confirm vehicle and equipment"},style=MaterialTheme.typography.labelSmall,color=if(issues>0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
                TextButton(onVehicle,colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.onSurface)) {Text("Vehicle & equipment")}
            }
        }
    }
}


@Composable private fun JobActivityList(events: List<JobActivityEvent>,loading: Boolean,error: String?,onRetry: () -> Unit) {
    LazyColumn(Modifier.fillMaxSize().testTag("job-activity"),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(0.dp)) {
        item {
            if(loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            error?.let {au.mainspring.nativeapp.ui.ErrorBanner(it,onRetry=onRetry)}
            if(!loading && error==null && events.isEmpty()) Text("No activity recorded yet",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        }
        items(events,key={it.id.ifBlank {it.createdAt+it.eventSummary}}) {event ->
            Column(Modifier.fillMaxWidth().padding(vertical=10.dp),verticalArrangement=Arrangement.spacedBy(2.dp)) {
                Text(formatShopDate(event.createdAt),style=Calibre.label,color=MaterialTheme.colorScheme.onSurfaceVariant)
                Text(event.eventSummary,style=MaterialTheme.typography.bodyMedium)
                event.actorEmail?.takeIf {it.isNotBlank()}?.let {Text(it,style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
            }
            HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

@Composable private fun KeyLookupDialog(job: AutoKeyJobRead,state: AutoKeyJobDetailUiState,onSearch: (String,String,String) -> Unit,onApply: (KeySpecMatch,String) -> Unit,onClose: () -> Unit) {
    var make by rememberSaveable(job.id) {mutableStateOf(job.vehicleMake.orEmpty())}
    var model by rememberSaveable(job.id) {mutableStateOf(job.vehicleModel.orEmpty())}
    var year by rememberSaveable(job.id) {mutableStateOf(job.vehicleYear?.toString().orEmpty())}
    val busy=state.keySearchLoading || state.keyApplyBusy
    LaunchedEffect(Unit) {if(!state.keySearched && (make.trim().length>=2 || model.trim().length>=2)) onSearch(make,model,year)}
    LaunchedEffect(state.keyApplied) {if(state.keyApplied) onClose()}
    AlertDialog(onDismissRequest={if(!state.keyApplyBusy) onClose()},title={Text("Look up key details")},
        text={
            LazyColumn(Modifier.heightIn(max=480.dp).testTag("key-lookup-results"),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                item {
                    Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
                        Text("Refine make, model and year, then apply a match to fill the vehicle, key type, chip, blade code and notes.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                        au.mainspring.nativeapp.ui.AtelierTextField(make,{make=it},label={Text("Make")},modifier=Modifier.fillMaxWidth(),singleLine=true)
                        au.mainspring.nativeapp.ui.AtelierTextField(model,{model=it},label={Text("Model")},modifier=Modifier.fillMaxWidth(),singleLine=true)
                        au.mainspring.nativeapp.ui.AtelierTextField(year,{year=it.filter(Char::isDigit).take(4)},label={Text("Year (optional)")},modifier=Modifier.fillMaxWidth(),singleLine=true)
                        Button({onSearch(make,model,year)},enabled=!busy,modifier=Modifier.fillMaxWidth()) {Text(if(state.keySearchLoading) "Searching…" else "Search")}
                        if(busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                        state.keySearchError?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)}
                        if(state.keySearched && state.keyMatches.isEmpty() && state.keySearchError==null) Text("No matches. Try fewer letters or remove the year.",style=MaterialTheme.typography.bodySmall)
                    }
                }
                items(state.keyMatches.size) {index ->
                    val m=state.keyMatches[index]
                    FlatPanel {
                        Text(m.label.ifBlank {listOf(m.vehicleMake,m.vehicleModel).joinToString(" ")},style=MaterialTheme.typography.titleSmall)
                        m.yearsLabel?.takeIf {it.isNotBlank()}?.let {Text(it,style=Calibre.label,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                        listOf("Key type" to m.keyType,"Transponder" to m.chipType,"Blade" to m.blankCodes().joinToString(", ")).forEach {(label,value)->if(!value.isNullOrBlank()) DetailRow(label,value)}
                        m.techNotes?.takeIf {it.isNotBlank()}?.let {Text(it,style=MaterialTheme.typography.bodySmall,maxLines=6,overflow=androidx.compose.ui.text.style.TextOverflow.Ellipsis)}
                        val badges=listOfNotNull(m.aklComplexity?.takeIf {it.isNotBlank()}?.let {"AKL ${it.replace('_',' ')}"},"BSU required".takeIf {m.bsuRequired==true},"PIN required".takeIf {m.pinRequired==true},"Dealer only".takeIf {m.dealerRequired==true},"EEPROM".takeIf {m.eepromRequired==true && m.obdProgrammable!=true})
                        if(badges.isNotEmpty()) Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(6.dp)) {
                            badges.forEach {badge->Surface(shape=MaterialTheme.shapes.small,color=MaterialTheme.colorScheme.secondaryContainer) {Text(badge.uppercase(),Modifier.padding(horizontal=8.dp,vertical=3.dp),style=Calibre.label)}}
                        }
                        Button({onApply(m,year)},enabled=!busy,modifier=Modifier.fillMaxWidth().testTag("key-match-$index")) {Text(if(state.keyApplyBusy) "Applying…" else "Apply to job")}
                    }
                }
            }
        },
        confirmButton={TextButton(onClose,enabled=!state.keyApplyBusy) {Text("Close")}})
}
