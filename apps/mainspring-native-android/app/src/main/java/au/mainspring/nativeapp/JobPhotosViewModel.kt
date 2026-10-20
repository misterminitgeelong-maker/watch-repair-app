package au.mainspring.nativeapp

import android.content.Context
import android.net.Uri
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import com.google.gson.Gson
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import retrofit2.HttpException
import java.util.UUID

data class JobPhotoDraft(val uri: String = "", val label: String = "Job photo", val filename: String = "", val cameraUri: String = "")
data class JobPhotosState(val draft: JobPhotoDraft = JobPhotoDraft(), val files: List<AttachmentRead> = emptyList(),
    val busy: Boolean = false, val loading: Boolean = false, val uncertain: Boolean = false,
    val historyChecked: Boolean = false, val hasMore: Boolean = false, val error: String? = null, val info: String? = null)

class JobPhotosViewModel(private val resource: String, private val id: String) : ViewModel() {
    init { require(resource in setOf("repair-jobs", "shoe-repair-jobs", "auto-key-jobs")) }
    private val api = ApiClient.api
    private val origin = ApiClient.getEffectiveBaseUrl()
    private val drafts = TokenStore.bindDrafts()
    private val key = "job-photo/$resource/$id"
    private val restored = try { Gson().fromJson(drafts.loadMessageDraft(key), JobPhotoDraft::class.java) ?: JobPhotoDraft() } catch(_: Exception) { JobPhotoDraft() }
    private val mutable = MutableStateFlow(JobPhotosState(draft = restored, uncertain = drafts.pendingOperation(key)))
    val state = mutable.asStateFlow()
    init { refresh() }
    private fun persist(value: JobPhotoDraft) { drafts.saveMessageDraft(key, Gson().toJson(value)); mutable.update { it.copy(draft = value) } }
    fun select(value: String) {
        if(mutable.value.busy || mutable.value.uncertain) return
        val old = mutable.value.draft
        persist(old.copy(uri = value, filename = if(value.isBlank()) "" else "mainspring-${UUID.randomUUID()}.jpg", cameraUri = ""))
        listOf(old.uri, old.cameraUri).filter { it != value }.forEach(::deleteUnusedOwnedPhoto)
    }
    fun label(value: String) { if(!mutable.value.busy && !mutable.value.uncertain) persist(mutable.value.draft.copy(label = value)) }
    fun cameraStarted(uri: String) {
        if(mutable.value.busy || mutable.value.uncertain) return
        val old = mutable.value.draft.cameraUri
        persist(mutable.value.draft.copy(cameraUri = uri)); if(old != uri) deleteUnusedOwnedPhoto(old)
        TokenStore.flushDraftCheckpoint()
    }
    fun cameraFinished(success: Boolean) {
        val uri = mutable.value.draft.cameraUri
        if(success && uri.isNotBlank()) select(uri)
        else { persist(mutable.value.draft.copy(cameraUri = "")); deleteUnusedOwnedPhoto(uri) }
    }
    private suspend fun files(offset: Int = 0) = api.listAttachments(
        repairJobId = id.takeIf { resource == "repair-jobs" },
        shoeRepairJobId = id.takeIf { resource == "shoe-repair-jobs" },
        autoKeyJobId = id.takeIf { resource == "auto-key-jobs" }, offset = offset)
    fun refresh() = fetch(false)
    fun loadMore() { if(mutable.value.hasMore) fetch(true) }
    private fun fetch(append: Boolean) {
        if(mutable.value.loading || mutable.value.busy) return
        mutable.update { it.copy(loading = true, historyChecked = false, error = null) }
        viewModelScope.launch {
            try {
                val rows = files(if(append) mutable.value.files.size else 0); val draft = mutable.value.draft
                if(mutable.value.uncertain && draft.filename.isNotBlank() && rows.any { it.fileName == draft.filename }) {
                    drafts.setPendingOperation(key, false); persist(draft.copy(uri = "", filename = "")); deleteUnusedOwnedPhoto(draft.uri)
                    mutable.update { it.copy(uncertain = false, info = "Recovered the photo already saved on this job.") }
                }
                mutable.update { it.copy(files = if(append) (it.files + rows).distinctBy { file -> file.id } else rows, hasMore = rows.size == 50, loading = false, historyChecked = true) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    /** Uploads any file (PDF, document, image...) as-is, as the web "Upload File" button does. */
    fun uploadFile(context: Context, uri: Uri) {
        val snapshot = mutable.value
        if(snapshot.loading || snapshot.busy || snapshot.uncertain) return
        mutable.update { it.copy(busy = true, error = null, info = null) }
        viewModelScope.launch {
            try {
                val resolver = context.contentResolver
                val name = withContext(Dispatchers.IO) {
                    resolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c -> if(c.moveToFirst()) c.getString(0) else null }
                } ?: "file-${UUID.randomUUID()}"
                val type = resolver.getType(uri) ?: "application/octet-stream"
                val bytes = withContext(Dispatchers.IO) { resolver.openInputStream(uri)?.use { it.readBytes() } ?: error("Could not read that file.") }
                require(bytes.size <= MAX_FILE_BYTES) { "That file is larger than 25 MB." }
                val part = MultipartBody.Part.createFormData("file", name, bytes.toRequestBody(type.toMediaType()))
                val saved = api.uploadJobPhoto(part, watchId = id.takeIf { resource == "repair-jobs" }, shoeId = id.takeIf { resource == "shoe-repair-jobs" },
                    mobileId = id.takeIf { resource == "auto-key-jobs" }, label = name.take(64))
                mutable.update { it.copy(files = (listOf(saved) + it.files).distinctBy { row -> row.id }, info = "File saved on this job.") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
            finally { mutable.update { it.copy(busy = false) } }
        }
    }
    fun checkedFiles() {
        if(!mutable.value.historyChecked || mutable.value.busy) return
        drafts.setPendingOperation(key, false); mutable.update { it.copy(uncertain = false) }
    }
    suspend fun downloadLink(file: AttachmentRead): String = absolutizeApiUrl(origin, api.getAttachmentDownloadLink(file.storageKey).downloadUrl)
    fun upload(context: Context) {
        val snapshot = mutable.value
        if(snapshot.loading || snapshot.busy || snapshot.uncertain || snapshot.draft.uri.isBlank()) return
        mutable.update { it.copy(busy = true, error = null, info = null) }
        viewModelScope.launch {
            var submitted = false
            try {
                require(snapshot.draft.label.trim().length <= 64) { "Keep the photo label within 64 characters." }
                val bytes = withContext(Dispatchers.IO) { preparedIntakePhoto(context, Uri.parse(snapshot.draft.uri)) }
                check(drafts.setPendingOperation(key, true)) { "Could not save the photo checkpoint. Check device storage and sign in before continuing." }
                submitted = true
                val part = MultipartBody.Part.createFormData("file", snapshot.draft.filename, bytes.toRequestBody("image/jpeg".toMediaType()))
                val saved = api.uploadJobPhoto(part, watchId = id.takeIf { resource == "repair-jobs" }, shoeId = id.takeIf { resource == "shoe-repair-jobs" },
                    mobileId = id.takeIf { resource == "auto-key-jobs" }, label = snapshot.draft.label.trim().ifBlank { "Job photo" })
                persist(snapshot.draft.copy(uri = "", filename = "")); drafts.setPendingOperation(key, false); deleteUnusedOwnedPhoto(snapshot.draft.uri)
                mutable.update { it.copy(files = (listOf(saved) + it.files).distinctBy { row -> row.id }, info = "Photo saved on this job.") }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val unknown = submitted && (e !is HttpException || e.code() >= 500)
                drafts.setPendingOperation(key, unknown)
                mutable.update { it.copy(uncertain = unknown, historyChecked = false, error = if(unknown) "The upload result is unknown. Refresh job files before uploading again. ${e.userMessage()}" else e.userMessage()) }
            } finally { mutable.update { it.copy(busy = false) } }
        }
    }
    companion object { const val MAX_FILE_BYTES = 25 * 1024 * 1024; fun factory(resource: String, id: String) = object: ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>): T = JobPhotosViewModel(resource, id) as T
    } }
}
