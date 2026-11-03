package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class IntegrationsState(
    val loading: Boolean = true, val busy: Boolean = false,
    val keys: List<TenantApiKey> = emptyList(), val webhooks: List<TenantWebhook> = emptyList(),
    /** The secret of a key created in this session. Shown once; the server never returns it again. */
    val createdKey: ApiKeyCreated? = null,
    val info: String? = null, val error: String? = null, val allowed: Boolean = true,
)

/** The web default for a new webhook: the two events most shops want. */
const val DEFAULT_WEBHOOK_EVENTS = "quote_approved,job_created"

/** Splits the comma-separated event field the way the web form does: trimmed, blanks dropped. */
fun parseWebhookEvents(text: String): List<String> = text.split(',').map { it.trim() }.filter { it.isNotEmpty() }

/** Shop API keys and outbound webhooks (web `TenantQolSettings`). Manager and above can create and remove. */
class IntegrationsViewModel(private val api: IntegrationsApi = ApiClient.service(IntegrationsApi::class.java)) : ViewModel() {
    private val mutable = MutableStateFlow(IntegrationsState(allowed = TokenStore.canManageInvoices()))
    val state = mutable.asStateFlow()
    init { refresh() }

    fun refresh() {
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val keys = api.apiKeys(); val hooks = api.webhooks()
                mutable.update { it.copy(loading = false, keys = keys, webhooks = hooks) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = "Could not load integrations. ${e.userMessage()}") } }
        }
    }

    private fun act(failure: String, block: suspend () -> Unit) {
        if(mutable.value.busy || !mutable.value.allowed) return
        mutable.update { it.copy(busy = true, info = null, error = null) }
        viewModelScope.launch {
            try { block() }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(error = "$failure ${e.userMessage()}") } }
            finally { mutable.update { it.copy(busy = false) } }
        }
    }

    fun createKey(name: String) {
        val trimmed = name.trim()
        if(trimmed.isEmpty()) { mutable.update { it.copy(error = "Give the key a name.") }; return }
        if(trimmed.length > 120) { mutable.update { it.copy(error = "Key names can be up to 120 characters.") }; return }
        act("Could not create the key.") {
            val created = api.createApiKey(ApiKeyCreateBody(trimmed))
            val keys = api.apiKeys()
            mutable.update { it.copy(createdKey = created, keys = keys, info = "API key created. Copy it now; it is not shown again.") }
        }
    }
    fun dismissCreatedKey() { mutable.update { it.copy(createdKey = null) } }

    fun revokeKey(id: String) = act("Could not revoke the key.") {
        val response = api.revokeApiKey(id)
        if(!response.isSuccessful) throw retrofit2.HttpException(response)
        mutable.update { it.copy(keys = it.keys.filterNot { k -> k.id == id }, createdKey = it.createdKey?.takeIf { k -> k.id != id }, info = "API key revoked.") }
    }

    fun addWebhook(url: String, events: String) {
        val trimmed = url.trim(); val types = parseWebhookEvents(events)
        if(!trimmed.startsWith("https://")) { mutable.update { it.copy(error = "Enter the full https:// address that should receive events.") }; return }
        if(trimmed.length > 512) { mutable.update { it.copy(error = "Webhook addresses can be up to 512 characters.") }; return }
        if(types.isEmpty()) { mutable.update { it.copy(error = "Choose at least one event, or * for all of them.") }; return }
        act("Could not add the webhook.") {
            val hook = api.createWebhook(WebhookCreateBody(trimmed, types))
            mutable.update { it.copy(webhooks = listOf(hook) + it.webhooks, info = "Webhook added.") }
        }
    }

    fun removeWebhook(id: String) = act("Could not remove the webhook.") {
        val response = api.deleteWebhook(id)
        if(!response.isSuccessful) throw retrofit2.HttpException(response)
        mutable.update { it.copy(webhooks = it.webhooks.filterNot { h -> h.id == id }, info = "Webhook removed.") }
    }
}
