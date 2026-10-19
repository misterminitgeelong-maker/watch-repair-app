package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.time.LocalDate
import java.time.ZoneId

data class PlannerState(val start: LocalDate,val loading: Boolean=false,val busy: Boolean=false,val error: String?=null,
    val technicians: List<TeamUser> = emptyList(),val jobs: List<AutoKeyJobRead> = emptyList(),val unscheduled: List<AutoKeyJobRead> = emptyList(),val total: Int=0,
    val uncertain: Boolean=false,val reviewed: Boolean=false,val info: String?=null)
class WeekPlannerViewModel : ViewModel() {
    private val api=ApiClient.api
    private val drafts=TokenStore.bindDrafts()
    private val today=LocalDate.now(ZoneId.of(TokenStore.calendarTimezone()))
    private val mutable=MutableStateFlow(PlannerState(today.minusDays(today.dayOfWeek.value.toLong()-1),uncertain=drafts.pendingOperation("planner-move")))
    val state=mutable.asStateFlow()
    private var request: Job?=null
    init {refresh()}
    fun shift(weeks: Long) {if(mutable.value.busy) return;mutable.update {it.copy(start=it.start.plusWeeks(weeks))};reload(true)}
    fun refresh() = reload(false)
    private fun reload(preserveError: Boolean) {
        if(mutable.value.busy) return
        request?.cancel();val start=mutable.value.start
        mutable.update {it.copy(loading=true,error=if(preserveError) it.error else null,reviewed=false)}
        request=viewModelScope.launch {
            try {
                val first=api.mobileJobPage(directory="all",limit=100,dateField="scheduled",dateFrom=start.toString(),dateTo=start.plusDays(6).toString())
                val rows=first.items.toMutableList()
                while(rows.size<first.total && rows.size<1000) {
                    val page=api.mobileJobPage(directory="all",limit=100,offset=rows.size,dateField="scheduled",dateFrom=start.toString(),dateTo=start.plusDays(6).toString())
                    if(page.items.isEmpty()) break
                    rows.addAll(page.items)
                }
                val unscheduled=api.mobileJobPage(directory="active",focus="unscheduled",limit=25)
                val users=try {api.teamUsers()} catch(e: CancellationException) {throw e} catch(_: Exception) {emptyList()}
                mutable.update {it.copy(loading=false,technicians=users,jobs=rows.distinctBy {j->j.id},total=first.total,unscheduled=unscheduled.items,reviewed=true)}
            } catch(e: CancellationException) {throw e} catch(e: Exception) {mutable.update {it.copy(loading=false,error=e.userMessage())}}
        }
    }
    fun reviewMove() {if(!mutable.value.reviewed || mutable.value.loading || mutable.value.busy) return;drafts.setPendingOperation("planner-move",false);mutable.update {it.copy(uncertain=false)}}
    fun move(job: AutoKeyJobRead,time: String) {
        if(mutable.value.loading || mutable.value.busy || mutable.value.uncertain || !TokenStore.canWorkJobs()) return
        val parsed=try {scheduledTimeIso(time,TokenStore.calendarTimezone()) ?: throw IllegalArgumentException("Choose a booking time.")} catch(e: Exception) {mutable.update {it.copy(error=e.userMessage())};return}
        if(job.updatedAt==null) {mutable.update {it.copy(error="Refresh this job before moving its booking.")};return}
        drafts.saveMessageDraft("planner-move/details","${job.jobNumber}: $time")
        if(!drafts.setPendingOperation("planner-move",true)) return
        mutable.update {it.copy(busy=true,error=null,info=null)}
        viewModelScope.launch {
            try {
                api.updateMobileJob(job.id,JsonObject().apply {addProperty("scheduled_at",parsed)},job.updatedAt)
                drafts.setPendingOperation("planner-move",false)
                mutable.update {it.copy(info="Booking moved.")}
            } catch(e: CancellationException) {throw e} catch(e: Exception) {
                val unknown=e !is retrofit2.HttpException || e.code()>=500
                drafts.setPendingOperation("planner-move",unknown)
                mutable.update {it.copy(uncertain=unknown,error=if(unknown) "Booking move has no confirmed result. Refresh and inspect the job before retrying." else e.userMessage())}
            } finally {mutable.update {it.copy(busy=false)};reload(true)}
        }
    }
    fun pendingMove(): String=drafts.loadMessageDraft("planner-move/details")
}
