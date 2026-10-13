package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

data class MessageThreadState(val messages: List<JobThreadMessage> = emptyList(), val draft: String = "",
    val loading: Boolean = false, val sending: Boolean = false, val uncertain: Boolean = false, val historyChecked: Boolean = false, val error: String? = null)
class MessageThreadViewModel(private val resource: String, private val id: String): ViewModel() {
    private val api = au.mainspring.nativeapp.api.ApiClient.api
    private val drafts = au.mainspring.nativeapp.TokenStore.bindDrafts()
    init { require(resource in setOf("repair-jobs", "shoe-repair-jobs", "auto-key-jobs")) }
    private val key = "$resource/$id"
    private val mutable = MutableStateFlow(MessageThreadState(draft = drafts.loadMessageDraft(key), uncertain = drafts.pendingOperation(key)))
    val state = mutable.asStateFlow()
    fun setDraft(text: String) { mutable.update { it.copy(draft = text) }; drafts.saveMessageDraft(key, text) }
    fun refresh() {
        if(mutable.value.loading || mutable.value.sending) return
        mutable.update { it.copy(loading = true) }
        viewModelScope.launch {
            try { val messages = api.messages(resource, id); mutable.update { it.copy(loading = false, historyChecked = true, error = null, messages = messages.sortedBy { m -> m.createdAt }) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not refresh messages. ${e.userMessage()}") } }
        }
    }
    fun send() {
        val text = mutable.value.draft.trim()
        if(mutable.value.sending || mutable.value.uncertain || text.isBlank()) return
        if(!drafts.setPendingOperation(key, true)) { mutable.update { it.copy(error = "Could not save the message checkpoint. Check device storage and sign in before continuing.") }; return }
        mutable.update { it.copy(sending = true, error = null) }
        viewModelScope.launch {
            try {
                val message = api.sendMessage(resource, id, MessageCreate(text))
                drafts.setPendingOperation(key, false)
                setDraft("")
                mutable.update { it.copy(sending = false, messages = (it.messages + message).distinctBy { m -> m.id }.sortedBy { m -> m.createdAt }) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { val unknown = e !is retrofit2.HttpException || e.code() >= 500
                drafts.setPendingOperation(key, unknown)
                mutable.update { it.copy(sending = false, uncertain = unknown, historyChecked = false,
                error = "Could not confirm delivery. Refresh and check the conversation before sending this message again. ${e.userMessage()}") } }
        }
    }
    fun acknowledgeHistory() { if(!mutable.value.historyChecked) return; drafts.setPendingOperation(key, false); mutable.update { it.copy(uncertain = false) } }
    companion object { fun factory(resource: String, id: String) = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = MessageThreadViewModel(resource, id) as T
    } }
}

