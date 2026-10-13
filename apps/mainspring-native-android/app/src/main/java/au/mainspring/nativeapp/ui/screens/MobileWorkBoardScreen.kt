package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import kotlinx.coroutines.launch
import androidx.compose.foundation.background
import androidx.compose.foundation.verticalScroll
import au.mainspring.nativeapp.api.AutoKeyJobRead
import au.mainspring.nativeapp.ui.*
import java.time.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MobileWorkBoardScreen(apiBaseUrl: String,onBack: () -> Unit,onOpenJob: (String) -> Unit,onNewJob: () -> Unit,onNavigate: (String)->Unit) {
    var mode by rememberSaveable {mutableStateOf("list")}
    var selected by rememberSaveable {mutableStateOf<String?>(null)}
    Scaffold(
        topBar={au.mainspring.nativeapp.ui.AtelierTopAppBar(title={Text("Mobile services",style=MaterialTheme.typography.titleLarge)},navigationIcon={au.mainspring.nativeapp.ui.BackButton(onBack)},
            actions={TextButton({onNavigate("route")},modifier=Modifier.heightIn(min=48.dp)) {Text("Map")}})},
        floatingActionButton={if(TokenStore.canWorkJobs()) ExtendedFloatingActionButton(onClick=onNewJob,containerColor=MaterialTheme.colorScheme.primary,contentColor=MaterialTheme.colorScheme.onPrimary) {Text("New job",style=MaterialTheme.typography.labelLarge)}},
    ) {padding->
    Column(Modifier.fillMaxSize().padding(padding)) {
        FilterRow(listOf("list" to "List","board" to "Kanban","planner" to "Planner"),mode,{mode=it ?: "list"})
        BoxWithConstraints(Modifier.weight(1f)) {
            when(mode) {
                "board" -> MobileKanbanScreen(onBack,onOpenJob,onNewJob)
                "planner" -> WeekPlannerScreen(onBack,onOpenJob)
                else -> if(maxWidth>=720.dp) Row(Modifier.fillMaxSize()) {
                    Box(Modifier.width(320.dp)) {AutoKeyJobsScreen(onBack,{selected=it},onNewJob,embedded=true)}
                    VerticalDivider()
                    Box(Modifier.weight(1f)) {
                        selected?.let {id->AutoKeyJobDetailScreen(id,apiBaseUrl,{selected=null},{onNavigate("messages/auto-key-jobs/$id")},{onNavigate("mobileFinance/$id?business=$it")},
                            {onNavigate("mobileEdit/$id")},onArrival={onNavigate("arrivalMessage/$id")},onSignature={onNavigate("quoteSignature/$id/$it")},embedded=true)}
                            ?: Column(Modifier.padding(32.dp)) {Text("Select a job",style=MaterialTheme.typography.headlineMedium);Text("View its details alongside your job list.")}
                    }
                } else AutoKeyJobsScreen(onBack,onOpenJob,onNewJob,embedded=true)
            }
        }
    }
    }
}

private fun boardColumn(status: String)=when(status) {
    "awaiting_quote","awaiting_customer_details"->"Awaiting quote"
    "quote_sent","awaiting_go_ahead"->"Quote sent"
    "booked","booking_confirmed","awaiting_booking_confirmation","pending_booking","go_ahead","booking_on_hold","job_delayed","awaiting_parts"->"Booked"
    "en_route","on_site","working_on","service"->"In the field"
    "work_completed","completed","booking_completed","awaiting_collection"->"Completed"
    "invoice_paid","collected"->"Paid"
    else->"Other"
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable private fun MobileKanbanScreen(onBack: ()->Unit,onJob: (String)->Unit,onNew: ()->Unit,model: AutoKeyJobsViewModel=viewModel(key="kanban")) {
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(model) {model.directory("all")}
    Scaffold(contentWindowInsets=WindowInsets(0,0,0,0),containerColor=androidx.compose.ui.graphics.Color.Transparent) {padding->
        Column(Modifier.fillMaxSize().padding(padding)) {
            au.mainspring.nativeapp.ui.AtelierTextField(state.query,model::query,label={Text("Search jobs")},modifier=Modifier.fillMaxWidth().padding(12.dp),singleLine=true)
            Text("${state.jobs.size} of ${state.total} jobs loaded",Modifier.padding(horizontal=12.dp),style=MaterialTheme.typography.bodySmall)
            state.error?.let {Text(it,Modifier.padding(12.dp),color=MaterialTheme.colorScheme.error)}
            if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            Row(Modifier.weight(1f).horizontalScroll(rememberScrollState()).padding(12.dp),horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                listOf("Awaiting quote","Quote sent","Booked","In the field","Completed","Paid","Other").forEach {label->
                    val rows=state.jobs.filter {boardColumn(it.status)==label}
                    Column(Modifier.width(240.dp)) {
                        SectionLabel("$label · ${rows.size}")
                        LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp)) {items(rows,key={it.id}) {job->FlatPanel {
                            Text(job.title,style=MaterialTheme.typography.titleSmall)
                            Text(job.customerName ?: job.jobNumber,style=MaterialTheme.typography.bodySmall)
                            job.scheduledAt?.let {Text(formatShopDate(it),style=MaterialTheme.typography.bodySmall)}
                            StatusPill(job.status)
                            TextButton({onJob(job.id)}) {Text("Open job")}
                        } } }
                    }
                }
            }
            if(state.jobs.size<state.total) Button(model::loadMore,enabled=!state.loading,modifier=Modifier.padding(12.dp),shape=MaterialTheme.shapes.small) {Text("Load more jobs")}
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable private fun WeekPlannerScreen(onBack: ()->Unit,onJob: (String)->Unit,model: WeekPlannerViewModel=viewModel()) {
    val state by model.state.collectAsStateWithLifecycle()
    var selecting by remember {mutableStateOf<AutoKeyJobRead?>(null)}
    var moving by remember {mutableStateOf<AutoKeyJobRead?>(null)}
    var technician by rememberSaveable {mutableStateOf("")}
    val vertical=rememberScrollState()
    val scope=rememberCoroutineScope()
    var time by rememberSaveable {mutableStateOf("")}
    val zone=ZoneId.of(TokenStore.calendarTimezone())
    RefreshOnResume(model::refresh)
    Scaffold(contentWindowInsets=WindowInsets(0,0,0,0),containerColor=androidx.compose.ui.graphics.Color.Transparent) {padding->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {TextButton({model.shift(-1)},enabled=!state.busy) {Text("Previous week")};TextButton({model.shift(1)},enabled=!state.busy) {Text("Next week")}}
            Text("${formatShopDate(state.start.toString())} - ${formatShopDate(state.start.plusDays(6).toString())}",Modifier.padding(horizontal=12.dp),style=MaterialTheme.typography.titleSmall)
            if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
            state.error?.let {Text(it,Modifier.padding(12.dp),color=MaterialTheme.colorScheme.error)}
            state.info?.let {Text(it,Modifier.padding(12.dp))}
            if(state.uncertain) Column(Modifier.padding(12.dp)) {Text(model.pendingMove());Text("Review the latest job booking before clearing the interrupted move.");OutlinedButton(model::reviewMove,enabled=state.reviewed && !state.loading && !state.busy) {Text("I have reviewed the booking")}}
            if(state.total>state.jobs.size) Text("Showing ${state.jobs.size} of ${state.total} bookings. Narrow the schedule from the job list.",Modifier.padding(12.dp),style=MaterialTheme.typography.bodySmall)
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal=12.dp),horizontalArrangement=Arrangement.spacedBy(6.dp)) {
                au.mainspring.nativeapp.ui.AtelierChip(technician.isBlank(),{technician=""},label={Text("All technicians")})
                au.mainspring.nativeapp.ui.AtelierChip(technician=="unassigned",{technician="unassigned"},label={Text("Unassigned")})
                state.technicians.filter {it.active || state.jobs.any {job->job.assignedUserId==it.id}}.forEach {user->au.mainspring.nativeapp.ui.AtelierChip(technician==user.id,{technician=user.id},label={Text(user.name)})}
            }
            selecting?.let {job->Row(Modifier.fillMaxWidth().padding(12.dp),horizontalArrangement=Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f)) {Text("Move ${job.jobNumber}",style=MaterialTheme.typography.titleSmall);Text("Choose a time slot, then confirm.",style=MaterialTheme.typography.bodySmall)}
                TextButton({moving=job;time=job.scheduledAt?.let {scheduleInputDate(it,zone.id)} ?: formatShopDate(state.start.toString())+" 09:00"}) {Text("Enter time")}
                TextButton({selecting=null}) {Text("Cancel")}
            } }
            val jobs=state.jobs.filter {technician.isBlank() || if(technician=="unassigned") it.assignedUserId==null else it.assignedUserId==technician}
            val unscheduled=state.unscheduled.filter {technician.isBlank() || if(technician=="unassigned") it.assignedUserId==null else it.assignedUserId==technician}
            Column(Modifier.weight(1f).horizontalScroll(rememberScrollState()).verticalScroll(vertical).padding(12.dp)) {
                Row {
                    Spacer(Modifier.width(52.dp))
                    (0L..6L).forEach {offset->SectionLabel(state.start.plusDays(offset).format(java.time.format.DateTimeFormatter.ofPattern("EEE d MMM")),Modifier.width(230.dp).padding(horizontal=8.dp))}
                }
                val hours=((8..17).toList()+jobs.mapNotNull {bookingInstant(it.scheduledAt)?.atZone(zone)?.hour}).distinct().sorted()
                hours.forEach {hour->Row(Modifier.height(IntrinsicSize.Min)) {
                    Text("%02d:00".format(hour),Modifier.width(52.dp).padding(top=10.dp),style=MaterialTheme.typography.labelSmall)
                    (0L..6L).forEach {offset->
                        val day=state.start.plusDays(offset)
                        val rows=jobs.filter {bookingInstant(it.scheduledAt)?.atZone(zone)?.let {booking->booking.toLocalDate()==day && booking.hour==hour}==true}.sortedBy {bookingInstant(it.scheduledAt)}
                        Column(Modifier.width(230.dp).fillMaxHeight().background(if(day==LocalDate.now(zone)) MaterialTheme.colorScheme.primaryContainer.copy(alpha=0.3f) else MaterialTheme.colorScheme.surface).padding(8.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                            if(selecting!=null) Row(horizontalArrangement=Arrangement.spacedBy(4.dp)) {
                                listOf(0,30).forEach {minute->OutlinedButton({
                                    moving=selecting
                                    time=day.format(java.time.format.DateTimeFormatter.ofPattern("dd/MM/uuuu"))+" "+"%02d:%02d".format(hour,minute)
                                },enabled=!state.busy && !state.uncertain,modifier=Modifier.weight(1f).testTag("planner-slot-$day-$hour-$minute"),contentPadding=PaddingValues(4.dp),shape=MaterialTheme.shapes.small) {Text("%02d:%02d".format(hour,minute),style=MaterialTheme.typography.labelSmall)}}
                            }
                            rows.forEach {job->FlatPanel {
                                Text(bookingInstant(job.scheduledAt)?.atZone(zone)?.format(java.time.format.DateTimeFormatter.ofPattern("HH:mm")).orEmpty(),style=MaterialTheme.typography.labelLarge)
                                Text(job.title,style=MaterialTheme.typography.titleSmall)
                                Text(state.technicians.firstOrNull {it.id==job.assignedUserId}?.name ?: "Unassigned",style=MaterialTheme.typography.bodySmall)
                                StatusPill(job.status)
                                Row {TextButton({onJob(job.id)}) {Text("Open")};if(TokenStore.canWorkJobs()) TextButton({selecting=job},enabled=!state.busy && !state.uncertain,modifier=Modifier.testTag("planner-move-${job.id}")) {Text("Move")}}
                            } }
                            if(rows.isEmpty() && selecting==null) Spacer(Modifier.height(64.dp))
                            HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
                        }
                    }
                } }
                SectionLabel("Unscheduled · ${unscheduled.size} loaded")
                Row(horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                    unscheduled.forEach {job->Box(Modifier.width(230.dp)) {FlatPanel {
                        Text(job.title,style=MaterialTheme.typography.titleSmall);StatusPill(job.status)
                        Row {TextButton({onJob(job.id)}) {Text("Open")};if(TokenStore.canWorkJobs()) TextButton({selecting=job;scope.launch {vertical.animateScrollTo(0)}},enabled=!state.busy && !state.uncertain) {Text("Move")}}
                    } } }
                }
            }
        }
    }
    moving?.let {job->AlertDialog(onDismissRequest={moving=null},title={Text("Move ${job.jobNumber}")},text={Column {
        Text(job.title);au.mainspring.nativeapp.ui.AtelierTextField(time,{time=it},label={Text("Booking: dd/MM/yyyy HH:mm")},singleLine=true)
        Text("Shop timezone: ${zone.id}",style=MaterialTheme.typography.bodySmall)
    }},confirmButton={TextButton({moving=null;selecting=null;model.move(job,time)},enabled=!state.loading && !state.busy && !state.uncertain) {Text("Confirm move")}},dismissButton={TextButton({moving=null}) {Text("Cancel")}})}
}
