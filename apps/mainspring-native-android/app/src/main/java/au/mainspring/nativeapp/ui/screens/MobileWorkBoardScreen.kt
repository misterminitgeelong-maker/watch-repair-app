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
import androidx.compose.ui.Alignment
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
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import java.time.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun MobileWorkBoardScreen(apiBaseUrl: String,onBack: () -> Unit,onOpenJob: (String) -> Unit,onNewJob: () -> Unit,onNavigate: (String)->Unit) {
    // Web default is the Kanban; a tablet keeps the master-detail list.
    val wide=androidx.compose.ui.platform.LocalConfiguration.current.screenWidthDp>=720
    var mode by rememberSaveable {mutableStateOf(if(wide) "list" else "board")}
    var selected by rememberSaveable {mutableStateOf<String?>(null)}
    Scaffold(contentWindowInsets=WindowInsets(0,0,0,0),containerColor=androidx.compose.ui.graphics.Color.Transparent,
        floatingActionButton={if(TokenStore.canWorkJobs()) NewJobFab(onNewJob)}) {padding->
    Column(Modifier.fillMaxSize().padding(padding)) {
        Column(Modifier.fillMaxWidth().padding(horizontal=16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
            ServiceTitle("Mobile Services",Modifier.padding(top=8.dp))
            var menuOpen by remember {mutableStateOf(false)}
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp),verticalAlignment=Alignment.CenterVertically) {
                Box {
                    WebButton(null,{menuOpen=true},icon="dots",tag="mobile-menu",description="More options")
                    DropdownMenu(menuOpen,{menuOpen=false}) {
                        DropdownMenuItem(text={Text("Map")},onClick={menuOpen=false;onNavigate("route")})
                        DropdownMenuItem(text={Text("Booking requests")},onClick={menuOpen=false;onNavigate("bookingRequests")})
                    }
                }
                if(TokenStore.canWorkJobs()) WebButton("New Job",onNewJob,primary=true,icon="plus",tag="new-job-ticket")
                WebButton("Send request",{onNavigate("sendBookingRequest")},icon="phone",tag="send-request")
            }
            ChipTabs(listOf(ToggleOption("jobs","Jobs & dispatch","tab-jobs"),ToggleOption("revenue","Revenue control","tab-revenue"),ToggleOption("team","Team","tab-team"),ToggleOption("finance","Finance report","tab-finance")),"jobs",
                {when(it) {"revenue"->onNavigate("revenueControl");"team"->onNavigate("team");"finance"->onNavigate("financeReport")}})
            WebSelect(when(mode) {"board"->"Kanban";"planner"->"Planner";else->"List"},listOf("board" to "Kanban","list" to "List","planner" to "Planner"),{mode=it},tag="view-select",description="Job view")
        }
        BoxWithConstraints(Modifier.weight(1f)) {
            when(mode) {
                "board" -> MobileKanbanScreen(onOpenJob)
                "planner" -> WeekPlannerScreen(onBack,onOpenJob)
                else -> if(maxWidth>=720.dp) Row(Modifier.fillMaxSize()) {
                    Box(Modifier.width(320.dp)) {AutoKeyJobsScreen(onBack,{selected=it},onNewJob,embedded=true,onOpenBookingRequests={onNavigate("bookingRequests")})}
                    VerticalDivider()
                    Box(Modifier.weight(1f)) {
                        selected?.let {id->AutoKeyJobDetailScreen(id,apiBaseUrl,{selected=null},{onNavigate("messages/auto-key-jobs/$id")},{onNavigate("mobileFinance/$id?business=$it")},
                            {onNavigate("mobileEdit/$id")},onArrival={onNavigate("arrivalMessage/$id")},onSignature={onNavigate("quoteSignature/$id/$it")},embedded=true)}
                            ?: Column(Modifier.padding(32.dp)) {Text("Select a job",style=MaterialTheme.typography.headlineMedium);Text("View its details alongside your job list.")}
                    }
                } else AutoKeyJobsScreen(onBack,onOpenJob,onNewJob,embedded=true,onOpenBookingRequests={onNavigate("bookingRequests")})
            }
        }
    }
    }
}

/** The web's active Mobile Services stages (frontend/src/components/kanban/columns.ts): label, statuses, top-edge colour, badge tint. */
private class MobileStage(val key: String,val label: String,val statuses: Set<String>,val color: androidx.compose.ui.graphics.Color,val tint: androidx.compose.ui.graphics.Color)
private val MOBILE_STAGES=listOf(
    MobileStage("awaiting_quote","Awaiting Quote",setOf("awaiting_quote","awaiting_customer_details"),androidx.compose.ui.graphics.Color(0xFF9A5F10),androidx.compose.ui.graphics.Color(0xFFFAEEDB)),
    MobileStage("quote_sent","Quote Sent",setOf("quote_sent","awaiting_go_ahead"),androidx.compose.ui.graphics.Color(0xFF2A5FA0),androidx.compose.ui.graphics.Color(0xFFEDF3FA)),
    MobileStage("awaiting_booking_confirmation","Awaiting Booking Confirmation",setOf("awaiting_booking_confirmation","pending_booking"),androidx.compose.ui.graphics.Color(0xFF3E6FB0),androidx.compose.ui.graphics.Color(0xFFE7F0FA)),
    MobileStage("booking_confirmed","Booking Confirmed",setOf("booking_confirmed","booked","go_ahead"),androidx.compose.ui.graphics.Color(0xFFB06010),androidx.compose.ui.graphics.Color(0xFFFFF0E0)),
    MobileStage("booking_on_hold","Booking on Hold",setOf("booking_on_hold","job_delayed","awaiting_parts"),androidx.compose.ui.graphics.Color(0xFFA84F1A),androidx.compose.ui.graphics.Color(0xFFFDE8D8)),
    MobileStage("in_field","In the Field",setOf("en_route","on_site","working_on","service"),androidx.compose.ui.graphics.Color(0xFF6A3FC9),androidx.compose.ui.graphics.Color(0xFFEDE5F5)),
    MobileStage("work_completed","Work Completed",setOf("work_completed","completed","booking_completed","awaiting_collection"),androidx.compose.ui.graphics.Color(0xFF1E7040),androidx.compose.ui.graphics.Color(0xFFE8F5ED)),
)

/** Web "Mobile Services - Kanban": heading, active-job caption and one coloured column per stage with web-style job cards. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable private fun MobileKanbanScreen(onJob: (String)->Unit,model: AutoKeyJobsViewModel=viewModel(key="kanban")) {
    val state by model.state.collectAsStateWithLifecycle()
    LaunchedEffect(model) {model.directory("active")}
    val byId=state.jobs.associateBy {it.id}
    val stages=MOBILE_STAGES.map {st->WebKanbanColumn(st.key,st.label,st.color,st.tint,state.jobs.filter {it.status in st.statuses}.map {BoardCard(it.id,it.title,it.customerName.orEmpty(),it.status)})}
    val active=stages.sumOf {it.cards.size}
    Box(Modifier.fillMaxSize()) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom=96.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        Column(Modifier.padding(horizontal=16.dp),verticalArrangement=Arrangement.spacedBy(2.dp)) {
            Text("Mobile Services \u2014 Kanban",style=MaterialTheme.typography.titleMedium,fontWeight=androidx.compose.ui.text.font.FontWeight.Bold)
            Text("$active active job${if(active==1) "" else "s"} across ${stages.size} stages",style=MaterialTheme.typography.bodyMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
        }
        state.error?.let {au.mainspring.nativeapp.ui.ErrorBanner(it,Modifier.padding(horizontal=16.dp),onRetry={model.refresh()})}
        if(state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        ZoomableBoard("mobile",stages.size,168.dp) {
        WebKanban(stages) {card,color->
            val job=byId[card.id] ?: return@WebKanban
            val vehicle=listOfNotNull(job.vehicleYear?.toString(),job.vehicleMake,job.vehicleModel).filter {it.isNotBlank()}.joinToString(" ")
            HoldMenuTicket(job.title, MOBILE_STAGES.firstOrNull {job.status in it.statuses}?.statuses?.first() ?: job.status, MOBILE_STAGES.map {it.statuses.first() to it.label}, TokenStore.canWorkJobs() && state.movingId==null, job.customerPhone, {onJob(job.id)}, {st,why->model.moveJob(job.id,st,MOBILE_STAGES.first {it.statuses.first()==st}.label,why)}) {
Surface(Modifier.fillMaxWidth().testTag("board-card-${job.id}"),shape=RoundedCornerShape(4.dp),color=MaterialTheme.colorScheme.surface,border=androidx.compose.foundation.BorderStroke(1.dp,MaterialTheme.colorScheme.outlineVariant)) {
                Column(Modifier.padding(8.dp),verticalArrangement=Arrangement.spacedBy(2.dp)) {
                    Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
                        Text(job.jobNumber,Modifier.weight(1f),style=MaterialTheme.typography.labelLarge,fontWeight=androidx.compose.ui.text.font.FontWeight.Bold,color=color,maxLines=1)
                        AgeChip("${daysInShop(job.createdAt)}d")
                    }
                    Text(job.title,style=MaterialTheme.typography.bodyMedium,fontWeight=androidx.compose.ui.text.font.FontWeight.SemiBold,maxLines=2)
                    if(vehicle.isNotBlank()) Text(vehicle,style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant,maxLines=1)
                    if(!job.customerName.isNullOrBlank()) Text(job.customerName,style=MaterialTheme.typography.bodySmall,maxLines=1)
                    job.scheduledAt?.let {DatePill(formatShopDate(it,TokenStore.calendarTimezone()),Modifier.padding(top=2.dp))}
                }
            }
}
        }
}
        if(state.jobs.size<state.total) SecondaryAction(model::loadMore,Modifier.padding(horizontal=16.dp),enabled=!state.loading) {Text("Load more jobs")}
    }
        BoardMoveToastBar(state.moveToast,{t->model.moveJob(t.id,t.from,au.mainspring.nativeapp.ui.statusLabel(t.from),null,false)},model::clearMoveToast,Modifier.align(Alignment.BottomCenter).padding(bottom=84.dp))
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
                                Row(horizontalArrangement=if(LocalCalibre.current) Arrangement.spacedBy(16.dp) else Arrangement.Start) {TextButton({onJob(job.id)}) {Text("Open")};if(TokenStore.canWorkJobs()) TextButton({selecting=job},enabled=!state.busy && !state.uncertain,modifier=Modifier.testTag("planner-move-${job.id}")) {Text("Move")}}
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
