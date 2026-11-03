package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.AutoKeyJobRead
import com.google.gson.Gson
import java.time.LocalDate
import java.time.ZoneId

/** Read-only snapshots share the encrypted, user/shop/session-bound draft store. */
class FieldSnapshots(private val drafts: TokenStore.BoundDrafts) {
    private val gson=Gson()
    fun job(id: String): AutoKeyJobRead? = try {
        gson.fromJson(drafts.loadMessageDraft("mobile-job-cache/$id"),AutoKeyJobRead::class.java)?.takeIf {it.id==id}
    } catch(_: Exception) {null}
    fun saveJob(job: AutoKeyJobRead) {
        val ids=try {gson.fromJson(drafts.loadMessageDraft("mobile-job-cache/index"),Array<String>::class.java)?.toList().orEmpty()} catch(_: Exception) {emptyList()}
        val recent=(listOf(job.id)+ids.filter {it!=job.id}).distinct()
        recent.drop(50).forEach {drafts.saveMessageDraft("mobile-job-cache/$it", "")}
        drafts.saveMessageDraft("mobile-job-cache/${job.id}",gson.toJson(job))
        drafts.saveMessageDraft("mobile-job-cache/index",gson.toJson(recent.take(50)))
    }
    private fun todayKey(tab: String)="today-cache/${LocalDate.now(ZoneId.of(TokenStore.calendarTimezone()))}/$tab"
    fun today(tab: String): TodayState? = try {
        gson.fromJson(drafts.loadMessageDraft(todayKey(tab)),TodayState::class.java)?.takeIf {it.tab==tab}?.copy(loading=true,offlineSnapshot=true,error=null)
    } catch(_: Exception) {null}
    fun saveToday(tab: String,state: TodayState) {
        val key=todayKey(tab)
        val previous=drafts.loadMessageDraft("today-cache/current/$tab")
        if(previous.isNotBlank() && previous!=key) drafts.saveMessageDraft(previous, "")
        drafts.saveMessageDraft(key,gson.toJson(state))
        drafts.saveMessageDraft("today-cache/current/$tab",key)
    }
}
