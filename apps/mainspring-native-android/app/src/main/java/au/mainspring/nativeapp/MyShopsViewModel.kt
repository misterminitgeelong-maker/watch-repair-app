package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import com.google.gson.JsonObject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class MyShopsState(val loading: Boolean = false, val busy: Boolean = false, val error: String? = null, val info: String? = null,
    val summary: MyShopsSummary? = null, val shops: List<ParentShop> = emptyList(), val total: Int = 0,
    val activity: List<ParentActivity> = emptyList(), val invitations: List<ShopLinkRequest> = emptyList(),
    val usage: ShopUsage? = null, val month: String = java.time.YearMonth.now(java.time.ZoneId.of(TokenStore.calendarTimezone())).toString(), val query: String = "",
    val unknown: Boolean = false, val reviewed: Boolean = false, val usageError: String? = null, val activityError: String? = null)
class MyShopsViewModel(private val api: MyShopsApi = ApiClient.service(MyShopsApi::class.java)) : ViewModel() {
    private val drafts = TokenStore.bindDrafts()
    private val checkpoint = "my-shops-write"
    private val mutable = MutableStateFlow(MyShopsState(unknown = drafts.pendingOperation(checkpoint)))
    val state = mutable.asStateFlow()
    private var request: Job? = null
    init { refresh() }
    fun refresh() { if(mutable.value.busy) return; request?.cancel(); request = viewModelScope.launch { load(false) } }
    fun query(value: String) { mutable.update { it.copy(query = value) }; request?.cancel(); request = viewModelScope.launch { delay(300); load(false) } }
    fun month(value: String) {
        if(!Regex("\\d{4}-\\d{2}").matches(value)) { mutable.update { it.copy(month = value) }; return }
        try { java.time.YearMonth.parse(value) } catch(_: Exception) { return }
        mutable.update { it.copy(month = value) }; refresh()
    }
    fun more() { if(mutable.value.loading || mutable.value.shops.size >= mutable.value.total) return; request = viewModelScope.launch { load(true) } }
    private suspend fun load(append: Boolean) {
        val s = mutable.value
        mutable.update { it.copy(loading = true, error = null, usageError = null, activityError = null) }
        try {
            val invites = if(TokenStore.isOwner()) api.invitations() else emptyList()
            val summary = try { api.summary() } catch(e: retrofit2.HttpException) { if(e.code() == 404) null else throw e }
            if(summary == null) { mutable.update { it.copy(loading = false, summary = null, invitations = invites, reviewed = true) }; return }
            val page = api.shops(offset = if(append) s.shops.size else 0, search = s.query.trim().ifBlank { null })
            val activity = try { api.activity() } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(activityError = e.userMessage()) }; emptyList() }
            val usage = try { api.usage(s.month) } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(usageError = e.userMessage()) }; null }
            mutable.update { it.copy(loading = false, summary = summary, shops = if(append) (s.shops + page.sites).distinctBy { shop -> shop.id } else page.sites,
                total = page.total, activity = activity, invitations = invites, usage = usage, reviewed = true) }
        } catch(e: CancellationException) { throw e } catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
    }
    fun reviewed() { if(mutable.value.reviewed && !mutable.value.busy) { drafts.setPendingOperation(checkpoint, false); mutable.update { it.copy(unknown = false) } } }
    private fun write(success: String, onSuccess: () -> Unit = {}, block: suspend () -> Unit) {
        if(!TokenStore.isOwner() || mutable.value.busy || mutable.value.loading || mutable.value.unknown) return
        if(!drafts.setPendingOperation(checkpoint, true)) { mutable.update { it.copy(error = "Could not save the change checkpoint.") }; return }
        mutable.update { it.copy(busy = true, error = null, info = null, reviewed = false) }
        viewModelScope.launch { try {
            block(); drafts.setPendingOperation(checkpoint, false); mutable.update { it.copy(info = success) }; onSuccess(); load(false)
        } catch(e: CancellationException) { throw e } catch(e: Exception) {
            val definite = e is retrofit2.HttpException && e.code() in 400..499
            if(definite) drafts.setPendingOperation(checkpoint, false)
            mutable.update { it.copy(unknown = !definite, error = if(definite) e.userMessage() else "The result is uncertain. Refresh and review your shops and requests before trying again. ${e.userMessage()}") }
        } finally { mutable.update { it.copy(busy = false) } } }
    }
    fun save(create: Boolean, name: String, slug: String, email: String, number: String, plan: String, done: () -> Unit) {
        val error = when { slug.isBlank() -> "Enter the shop’s login ID."; create && name.isBlank() -> "Enter a shop name."; !create && email.isBlank() -> "Enter the shop owner’s email."; else -> null }
        if(error != null) { mutable.update { it.copy(error = error) }; return }
        val body = JsonObject().apply {
            addProperty("tenant_slug", slug.trim().lowercase()); if(number.isNotBlank()) addProperty("shop_number", number.trim())
            if(create) { addProperty("tenant_name", name.trim()); addProperty("plan_code", plan) } else addProperty("owner_email", email.trim().lowercase())
        }
        write(if(create) "Shop created." else "Link request sent. The shop owner must accept before it joins.", done) { if(create) api.create(body) else api.link(body) }
    }
    fun unlink(shop: ParentShop) = write("Shop removed from this account.") { api.unlink(shop.id) }
    fun invitation(request: ShopLinkRequest, accept: Boolean, onChanged: () -> Unit) = write(if(accept) "Network invitation accepted." else "Network invitation declined.", onChanged) { api.invitation(request.id, if(accept) "accept" else "decline") }
}
