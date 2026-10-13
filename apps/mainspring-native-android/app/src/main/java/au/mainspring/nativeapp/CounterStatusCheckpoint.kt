package au.mainspring.nativeapp

import com.google.gson.JsonObject
import com.google.gson.JsonParser

/** Counter status APIs append history and can notify customers, so uncertain writes must not replay. */
internal class CounterStatusCheckpoint(resource: String, id: String) {
    private val drafts = TokenStore.bindDrafts()
    private val key = "$resource-status/$id"
    val pending get() = drafts.pendingOperation(key)
    val description get() = runCatching {
        val request = JsonParser.parseString(drafts.loadMessageDraft(key)).asJsonObject
        "Requested ${request["status"].asString.replace('_',' ')}${request["note"]?.asString?.takeIf { it.isNotBlank() }?.let { " · $it" }.orEmpty()}"
    }.getOrDefault("")
    fun start(status: String, note: String?) {
        drafts.saveMessageDraft(key, JsonObject().apply { addProperty("status", status); addProperty("note", note.orEmpty()) }.toString())
        check(drafts.setPendingOperation(key, true)) { "Could not retain the status checkpoint. Check storage and sign in again." }
    }
    fun clear() { drafts.setPendingOperation(key, false); drafts.saveMessageDraft(key, "") }
}
