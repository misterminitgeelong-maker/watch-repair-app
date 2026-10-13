package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import androidx.compose.foundation.clickable
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.background
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.testTag
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
    model: TodayViewModel = viewModel(), onEnRoute: ((String) -> Unit)? = null) {
    val state by model.state.collectAsStateWithLifecycle()
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
                val next=nextFieldJob(state.jobs)
                if(next!=null) {
                    item {
                        val canEnRoute=onEnRoute!=null && !state.loading && !state.offlineSnapshot && TokenStore.canWorkJobs() && next.status in setOf("booked","booking_confirmed")
                        TodayJobRow(next,zone,onClick={onOpenJob(next.id)},nextLabel=if(state.tab in listOf("active","booked")) "Next up" else "First in queue") {
                            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                                Button({if(canEnRoute) onEnRoute?.invoke(next.id) else onOpenJob(next.id)},modifier=Modifier.weight(1f).heightIn(min=48.dp),shape=RoundedCornerShape(6.dp)) {Text(if(canEnRoute) "Mark En Route" else "Continue job")}
                                OutlinedButton({onOpenJob(next.id)},modifier=Modifier.heightIn(min=48.dp),shape=RoundedCornerShape(6.dp)) {Text("View details")}
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
}

private fun jobTime(job: AutoKeyJobRead,zone: ZoneId)=bookingInstant(job.scheduledAt)?.atZone(zone)?.format(DateTimeFormatter.ofPattern("HH:mm")) ?: "—"
private fun jobSubtitle(job: AutoKeyJobRead)=listOf(listOfNotNull(job.vehicleMake,job.vehicleModel,job.vehicleYear?.toString()).joinToString(" "),job.customerName.orEmpty()).filter {it.isNotBlank()}.joinToString(" · ")
@Composable private fun TodayJobRow(job: AutoKeyJobRead,zone: ZoneId,onClick: ()->Unit,nextLabel: String?=null,actions: (@Composable ()->Unit)?=null) {
    val timeWidth=if(androidx.compose.ui.platform.LocalDensity.current.fontScale>1.3f) 72.dp else 48.dp
    Surface(Modifier.fillMaxWidth().testTag(if(nextLabel!=null) "today-next-job" else "today-row-${job.id}").clickable(onClick=onClick),color=MaterialTheme.colorScheme.surface) {
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
                    if(job.priority=="urgent") StatusPill("urgent")
                }
                actions?.let {Spacer(Modifier.height(5.dp));it()}
                HorizontalDivider(Modifier.padding(top=8.dp),color=MaterialTheme.colorScheme.outlineVariant)
            }
        }
    }
}
