package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.clickable
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.AutoKeyJobRead
import au.mainspring.nativeapp.ui.*
import kotlinx.coroutines.delay
import java.time.*
import java.time.format.DateTimeFormatter
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun TodayScreen(onOpenJob: (String) -> Unit, onDirectory: () -> Unit, onNewJob: () -> Unit,
    model: TodayViewModel = viewModel(), onEnRoute: ((String) -> Unit)? = null, runSheet: Boolean = false) {
    val state by model.state.collectAsStateWithLifecycle()
    val run by model.runSheet.collectAsStateWithLifecycle()
    val context = androidx.compose.ui.platform.LocalContext.current
    var confirmComplete by remember { mutableStateOf<AutoKeyJobRead?>(null) }
    var contactError by remember { mutableStateOf<String?>(null) }
    val zone = ZoneId.of(TokenStore.calendarTimezone())
    var now by remember { mutableStateOf(Instant.now()) }
    RefreshOnResume(model::refresh)
    LaunchedEffect(zone) { while(true) { delay(60_000); val updated=Instant.now(); if(updated.atZone(zone).toLocalDate()!=now.atZone(zone).toLocalDate()) model.refresh(); now=updated } }
    val queues=listOf("active" to "Today","quote" to "Quotes","booked" to "Booked","completed" to "Unpaid")
    Scaffold(containerColor=MaterialTheme.colorScheme.surface,
        topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Column {
            Text("Today",style=MaterialTheme.typography.titleMedium,fontWeight=FontWeight.Bold)
            Text(now.atZone(zone).format(DateTimeFormatter.ofPattern("EEE, d MMM",Locale.UK)),style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        } },colors=TopAppBarDefaults.topAppBarColors(containerColor=MaterialTheme.colorScheme.surface),actions={
            TextButton(onDirectory) {Text("Search")}
            TextButton(model::refresh,enabled=!state.loading) { Text("Refresh") }
        }) },
        floatingActionButton = { if(TokenStore.canWorkJobs()) ExtendedFloatingActionButton(onClick=onNewJob,containerColor=MaterialTheme.colorScheme.primary,contentColor=MaterialTheme.colorScheme.onPrimary) {Text("New job",style=MaterialTheme.typography.labelLarge)} },
    ) {padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            TabRow(selectedTabIndex=queues.indexOfFirst {it.first==state.tab}.coerceAtLeast(0),containerColor=MaterialTheme.colorScheme.surface,divider={HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)}) {
                queues.forEach {(key,label)->Tab(selected=state.tab==key,onClick={model.tab(key)},selectedContentColor=MaterialTheme.colorScheme.primary,unselectedContentColor=MaterialTheme.colorScheme.onSurfaceVariant,text={Text(label,style=MaterialTheme.typography.labelLarge)})}
            }
            LazyColumn(Modifier.fillMaxSize().testTag("today-list"),contentPadding=PaddingValues(start=16.dp,end=16.dp,top=12.dp,bottom=96.dp),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                item {
                    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween,verticalAlignment=Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("${state.todayCount ?: "—"} ${if(state.todayCount==1) "job" else "jobs"} today · ${state.unscheduledCount ?: "—"} unscheduled",style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
                            Text("${state.unpaidCount ?: "—"} unpaid ${if(state.unpaidCount==1) "job" else "jobs"}",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                if(state.offlineSnapshot) item {Text("Saved schedule · reconnect for current job details",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                if(state.loading) item {LinearProgressIndicator(Modifier.fillMaxWidth())}
                state.error?.let {item {ErrorBanner(it,onRetry=model::refresh)}}
                if(state.truncated) item {Text("Showing the first 1,000 jobs. Use Search to narrow this queue.",style=MaterialTheme.typography.bodySmall)}
                if(runSheet) {
                    run.info?.let {item {Text(it,Modifier.testTag("run-sheet-info"),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.primary)}}
                    (run.error ?: contactError)?.let {item {ErrorBanner(it)}}
                    if(state.tab=="active") item {
                        Column(Modifier.fillMaxWidth().testTag("needs-action"),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                            SectionLabel("Needs action · ${attentionTotal(run.counts)}")
                            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                                NEEDS_ACTION_QUEUES.forEach {(key,label)->
                                    val count=run.counts[key] ?: 0
                                    OutlinedButton(onDirectory,modifier=Modifier.weight(1f).heightIn(min=48.dp).testTag("needs-action-$key"),contentPadding=PaddingValues(horizontal=4.dp)) {
                                        Text("$label $count",style=MaterialTheme.typography.labelMedium,maxLines=1,color=if(count>0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        }
                    }
                }
                val sheet=if(runSheet && state.tab=="active") runSheetOrder((run.field+state.jobs).distinctBy {it.id}) else state.jobs
                val next=if(runSheet) null else nextFieldJob(state.jobs)
                if(runSheet && sheet.isNotEmpty()) {
                    items(sheet,key={"run-${it.id}"}) {job->
                        TodayJobRow(job,zone,{onOpenJob(job.id)},late=job.id in run.lateIds) {
                            RunSheetActions(job,busy=run.movingId!=null,moving=run.movingId==job.id,online=!state.offlineSnapshot,
                                onCall={contactError=launchContact(context,android.content.Intent(android.content.Intent.ACTION_DIAL,android.net.Uri.parse("tel:"+dialDigits(job.customerPhone))))},
                                onRoute={directionsUri(job.jobAddress)?.let {contactError=launchContact(context,android.content.Intent(android.content.Intent.ACTION_VIEW,android.net.Uri.parse(it)))}},
                                onAdvance={target->if(needsCompletionConfirm(target)) confirmComplete=job else model.advance(job.id,target)},onOpen={onOpenJob(job.id)})
                        }
                    }
                } else if(next!=null) {
                    item {
                        val canEnRoute=onEnRoute!=null && !state.loading && !state.offlineSnapshot && TokenStore.canWorkJobs() && next.status in setOf("booked","booking_confirmed")
                        TodayJobRow(next,zone,onClick={onOpenJob(next.id)},nextLabel=if(state.tab in listOf("active","booked")) "Next up" else "First in queue") {
                            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                                Button({if(canEnRoute) onEnRoute?.invoke(next.id) else onOpenJob(next.id)},modifier=Modifier.weight(1f).heightIn(min=48.dp),shape=MaterialTheme.shapes.small) {Text(if(canEnRoute) "Mark En Route" else "Continue job")}
                                OutlinedButton({onOpenJob(next.id)},modifier=Modifier.heightIn(min=48.dp),shape=MaterialTheme.shapes.small) {Text("View details")}
                            }
                        }
                    }
                    items(state.jobs.filter {it.id!=next.id},key={"scheduled-${it.id}"}) {job->TodayJobRow(job,zone,{onOpenJob(job.id)})}
                } else if(!state.loading && state.error==null) item {
                    Column(Modifier.padding(vertical=24.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                        Text(if(state.tab=="active") "No appointments today" else "No jobs in this queue",style=MaterialTheme.typography.titleMedium)
                        Text(if(state.tab=="active") "Check unscheduled work or review unpaid jobs." else "Try another queue or browse your jobs.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                        TextButton(onDirectory) {Text("Browse all jobs")}
                        if(state.tab=="active" && (state.unpaidCount ?: 0)>0) TextButton({model.tab("completed")}) {Text("Review unpaid jobs")}
                    }
                }
                if(state.tab=="active") {
                    item {SectionLabel("Unscheduled · ${state.unscheduledCount ?: 0}")}
                    items(state.unscheduled,key={"unscheduled-${it.id}"}) {job->TodayJobRow(job,zone,{onOpenJob(job.id)})}
                    if((state.unscheduledCount ?: 0)>state.unscheduled.size) item {TextButton(onDirectory) {Text("View all unscheduled jobs")}}
                }
                item {TextButton(onDirectory) {Text("All jobs and scheduling")}}
            }
        }
    }
    confirmComplete?.let {job->
        AlertDialog(onDismissRequest={confirmComplete=null},title={Text("Complete job #${job.jobNumber}?")},
            text={Text("This marks the work complete. If the job has an approved quote, Mainspring may create the invoice and notify the customer through your shop settings. Payment is recorded separately.")},
            confirmButton={Button({confirmComplete=null;model.advance(job.id,"work_completed")},modifier=Modifier.heightIn(min=48.dp).testTag("run-complete-confirm")) {Text("Complete job")}},
            dismissButton={TextButton({confirmComplete=null},modifier=Modifier.heightIn(min=48.dp)) {Text("Cancel")}})
    }
}

private fun jobTime(job: AutoKeyJobRead,zone: ZoneId)=bookingInstant(job.scheduledAt)?.atZone(zone)?.format(DateTimeFormatter.ofPattern("HH:mm")) ?: "—"
private fun jobSubtitle(job: AutoKeyJobRead)=listOf(listOfNotNull(job.vehicleMake,job.vehicleModel,job.vehicleYear?.toString()).joinToString(" "),job.customerName.orEmpty()).filter {it.isNotBlank()}.joinToString(" · ")
/** Call, Route and the one-tap next step for a run-sheet row. Every target is 48dp and labelled for TalkBack. */
@Composable private fun RunSheetActions(job: AutoKeyJobRead,busy: Boolean,moving: Boolean,online: Boolean,onCall: ()->Unit,onRoute: ()->Unit,onAdvance: (String)->Unit,onOpen: ()->Unit) {
    val next=nextMobileStatus(job.status)
    val phone=dialDigits(job.customerPhone)
    val address=directionsUri(job.jobAddress)
    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(6.dp)) {
        OutlinedButton(onCall,enabled=phone.isNotEmpty(),modifier=Modifier.weight(1f).heightIn(min=48.dp).testTag("run-call-${job.id}").semantics {contentDescription=if(phone.isEmpty()) "No phone number" else "Call customer"},contentPadding=PaddingValues(horizontal=4.dp)) {Text(if(phone.isEmpty()) "No phone" else "Call",maxLines=1)}
        OutlinedButton(onRoute,enabled=address!=null,modifier=Modifier.weight(1f).heightIn(min=48.dp).testTag("run-route-${job.id}").semantics {contentDescription=if(address==null) "No address" else "Open route in maps"},contentPadding=PaddingValues(horizontal=4.dp)) {Text(if(address==null) "No address" else "Route",maxLines=1)}
        if(next!=null) Button({onAdvance(next)},enabled=!busy && online && TokenStore.canWorkJobs(),modifier=Modifier.weight(1.3f).heightIn(min=48.dp).testTag("run-advance-${job.id}"),shape=MaterialTheme.shapes.small,contentPadding=PaddingValues(horizontal=4.dp)) {Text(if(moving) "Saving\u2026" else quickStatusCopy(next),maxLines=1)}
        else Button(onOpen,modifier=Modifier.weight(1.3f).heightIn(min=48.dp).testTag("run-open-${job.id}"),shape=MaterialTheme.shapes.small,contentPadding=PaddingValues(horizontal=4.dp)) {Text("Open")}
    }
}

@Composable private fun TodayJobRow(job: AutoKeyJobRead,zone: ZoneId,onClick: ()->Unit,nextLabel: String?=null,late: Boolean=false,actions: (@Composable ()->Unit)?=null) {
    val timeWidth=if(androidx.compose.ui.platform.LocalDensity.current.fontScale>1.3f) 72.dp else 48.dp
    Surface(Modifier.fillMaxWidth().testTag(if(nextLabel!=null) "today-next-job" else "today-row-${job.id}").clickable(role = androidx.compose.ui.semantics.Role.Button, onClick = onClick),color=MaterialTheme.colorScheme.surface) {
        Row(Modifier.padding(vertical=12.dp).height(IntrinsicSize.Min),horizontalArrangement=Arrangement.spacedBy(10.dp)) {
            Text(jobTime(job,zone),Modifier.width(timeWidth),style=MaterialTheme.typography.labelLarge,fontWeight=FontWeight.Bold)
            Column(Modifier.width(8.dp).fillMaxHeight(),horizontalAlignment=Alignment.CenterHorizontally) {
                Box(Modifier.padding(top=5.dp).size(7.dp).background(MaterialTheme.colorScheme.primary,RoundedCornerShape(50)))
                Box(Modifier.width(1.dp).weight(1f).background(MaterialTheme.colorScheme.outlineVariant))
            }
            Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(3.dp)) {
                nextLabel?.let {Text(it,style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.primary)}
                Text(job.title,style=MaterialTheme.typography.titleSmall,fontWeight=FontWeight.SemiBold,maxLines=2,overflow=TextOverflow.Ellipsis)
                Text(jobSubtitle(job),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant,maxLines=2,overflow=TextOverflow.Ellipsis)
                job.jobAddress?.takeIf {it.isNotBlank()}?.let {Text(it,style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant,maxLines=2,overflow=TextOverflow.Ellipsis)}
                Row(horizontalArrangement=Arrangement.spacedBy(6.dp),verticalAlignment=Alignment.CenterVertically) {
                    StatusPill(job.status)
                    if(late) StatusPill("late")
                    if(job.priority=="urgent") StatusPill("urgent")
                }
                actions?.let {Spacer(Modifier.height(5.dp));it()}
                HorizontalDivider(Modifier.padding(top=8.dp),color=MaterialTheme.colorScheme.outlineVariant)
            }
        }
    }
}
