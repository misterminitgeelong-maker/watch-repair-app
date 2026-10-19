package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import com.google.gson.JsonObject
import java.time.LocalDate
import java.time.ZoneId

data class TeamState(val loading: Boolean = false,val busy: Boolean = false,val error: String? = null,val info: String? = null,
    val users: List<TeamUser> = emptyList(),val commissions: JsonObject? = null,val period: String = "month",val uncertain: Boolean = false,val reviewed: Boolean = false)

class TeamViewModel : ViewModel() {
    private val api=ApiClient.api
    private val drafts=TokenStore.bindDrafts()
    private val mutable=MutableStateFlow(TeamState(uncertain=drafts.pendingOperation("team-write")))
    val state=mutable.asStateFlow()
    init {refresh()}
    fun period(value: String) {if(value !in listOf("week","month","90")) return;mutable.update {it.copy(period=value)};reload(true)}
    fun refresh() = reload(false)
    private fun reload(preserveError: Boolean) {
        if(mutable.value.loading || mutable.value.busy) return
        mutable.update {it.copy(loading=true,error=if(preserveError) it.error else null,reviewed=false)}
        val period=mutable.value.period
        viewModelScope.launch {
            try {
                val users=api.teamUsers()
                mutable.update {it.copy(users=users)}
                val end=LocalDate.now(ZoneId.of(TokenStore.calendarTimezone()))
                val start=when(period) {"week"->end.minusDays(end.dayOfWeek.value.toLong()-1);"90"->end.minusDays(89);else->end.withDayOfMonth(1)}
                val commissions=try {api.mobileCommission(start.toString(),end.toString())} catch(e: CancellationException) {throw e} catch(_: Exception) {null}
                mutable.update {it.copy(loading=false,commissions=commissions,reviewed=true)}
            } catch(e: CancellationException) {throw e} catch(e: Exception) {mutable.update {it.copy(loading=false,error=e.userMessage())}}
        }
    }
    fun reviewedWrite() {if(!mutable.value.reviewed || mutable.value.busy) return;drafts.setPendingOperation("team-write",false);mutable.update {it.copy(uncertain=false)}}
    fun save(original: TeamUser?,name: String,email: String,password: String,role: String,active: Boolean,rules: String?) {
        if(!TokenStore.canManageTeam() || mutable.value.busy || mutable.value.loading || mutable.value.uncertain) return
        try {
            require(name.trim().isNotBlank() && name.length<=200) {"Enter a name of up to 200 characters."}
            require(role in listOf("owner","manager","tech","intake")) {"Choose an account role."}
            if(original==null) {require(email.contains('@') && email.length<=320) {"Enter the account's email."};require(password.length>=8) {"Use a password of at least 8 characters."}}
        } catch(e: Exception) {mutable.update {it.copy(error=e.userMessage())};return}
        if(!drafts.setPendingOperation("team-write",true)) return
        mutable.update {it.copy(busy=true,error=null,info=null)}
        viewModelScope.launch {
            try {
                val fields=JsonObject().apply {
                    addProperty("full_name",name.trim());addProperty("role",role)
                    if(original==null) {addProperty("email",email.trim());addProperty("password",password)} else addProperty("is_active",active)
                    if(rules!=null) addProperty("mobile_commission_rules_json",rules)
                }
                if(original!=null) {
                    val fresh=api.teamUsers().firstOrNull {it.id==original.id}
                    require(fresh==original) {"This account changed. Refresh and reopen it before saving."}
                    api.updateTeamUser(original.id,fields)
                } else api.createTeamUser(fields)
                drafts.setPendingOperation("team-write",false)
                mutable.update {it.copy(info="Account saved.")}
            } catch(e: CancellationException) {throw e} catch(e: Exception) {
                val unknown=e !is retrofit2.HttpException && e !is IllegalArgumentException || (e is retrofit2.HttpException && e.code()>=500)
                drafts.setPendingOperation("team-write",unknown)
                mutable.update {it.copy(uncertain=unknown,error=if(unknown) "The save has no confirmed result. Refresh and review the team before trying again." else e.userMessage())}
            } finally {mutable.update {it.copy(busy=false)};reload(true)}
        }
    }
    /** Permanently deletes a team account (owner only). Deactivating via Edit is the reversible option. */
    fun delete(user: TeamUser, ownerService: OwnerAdminApi = ApiClient.service(OwnerAdminApi::class.java)) {
        if(!TokenStore.canManageTeam() || mutable.value.busy || mutable.value.loading) return
        mutable.update {it.copy(busy=true,error=null,info=null)}
        viewModelScope.launch {
            try {
                val response=ownerService.deleteTeamUser(user.id)
                if(!response.isSuccessful) throw retrofit2.HttpException(response)
                mutable.update {it.copy(info="Account deleted.")}
            } catch(e: CancellationException) {throw e} catch(e: Exception) {mutable.update {it.copy(error=e.userMessage())}}
            finally {mutable.update {it.copy(busy=false)};reload(true)}
        }
    }
}
