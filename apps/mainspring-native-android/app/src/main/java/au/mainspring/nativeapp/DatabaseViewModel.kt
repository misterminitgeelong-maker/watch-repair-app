package au.mainspring.nativeapp

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.CsvImportResponse
import au.mainspring.nativeapp.api.DatabaseApi
import au.mainspring.nativeapp.api.GstSummaryResponse
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.time.LocalDate
import java.time.ZoneId

enum class DatabaseExport(val label: String, val fileName: String, val mime: String) {
    Jobs("Jobs CSV", "mainspring-jobs.csv", "text/csv"),
    Customers("Customers CSV", "mainspring-customers.csv", "text/csv"),
    Invoices("Invoices CSV", "mainspring-invoices.csv", "text/csv"),
    MyData("My data (JSON)", "mainspring-my-data.json", "application/json"),
}

/** A file chosen for import, held in memory (the server caps uploads at 25 MB) with a local row count (-1 for Excel). */
class PickedImport(val name: String, val bytes: ByteArray, val rowCount: Int, val isExcel: Boolean)

data class DatabaseState(
    val allowed: Boolean = true,
    val period: String = "month",
    val gstLoading: Boolean = false,
    val gst: GstSummaryResponse? = null,
    val gstError: String? = null,
    val exportBusy: DatabaseExport? = null,
    val exportInfo: String? = null,
    val target: String = "watch",
    val sheetName: String = "",
    val picked: PickedImport? = null,
    val importBusy: Boolean = false,
    val importResult: CsvImportResponse? = null,
    val importError: String? = null,
)

const val IMPORT_MAX_BYTES = 25 * 1024 * 1024

/** Rows in a CSV, excluding the header and blank lines; quoted newlines do not start a new row. */
fun countCsvRows(bytes: ByteArray): Int {
    var inQuotes = false; var rows = 0; var lineHasContent = false
    for(b in bytes) {
        val c = b.toInt().toChar()
        when {
            c == '"' -> { inQuotes = !inQuotes; lineHasContent = true }
            c == '\n' && !inQuotes -> { if(lineHasContent) rows++; lineHasContent = false }
            c == '\r' || c == ' ' -> {}
            else -> lineHasContent = true
        }
    }
    if(lineHasContent) rows++
    return maxOf(rows - 1, 0)
}

class DatabaseViewModel(private val api: DatabaseApi = ApiClient.service(DatabaseApi::class.java)) : ViewModel() {
    private val mutable = MutableStateFlow(DatabaseState(allowed = TokenStore.canManageInvoices()))
    val state = mutable.asStateFlow()
    private var gstJob: Job? = null

    init { if(state.value.allowed) loadGst() }

    fun selectPeriod(period: String) {
        if(period !in listOf("day", "week", "month", "quarter")) return
        mutable.update { it.copy(period = period) }; loadGst()
    }

    fun loadGst() {
        if(!TokenStore.canManageInvoices()) { mutable.update { it.copy(allowed = false) }; return }
        gstJob?.cancel()
        val period = state.value.period
        mutable.update { it.copy(gstLoading = true, gstError = null) }
        gstJob = viewModelScope.launch {
            try {
                val today = LocalDate.now(ZoneId.of(TokenStore.calendarTimezone())).toString()
                val result = api.getGstSummary(period, today)
                mutable.update { it.copy(gst = result, gstLoading = false) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(gstLoading = false, gst = null, gstError = e.userMessage()) } }
        }
    }

    /** Download the export body; the caller writes it to the chosen document. */
    suspend fun download(kind: DatabaseExport): ByteArray = withContext(Dispatchers.IO) {
        check(TokenStore.canManageInvoices()) { "Exports require an owner or manager account." }
        val body = when(kind) {
            DatabaseExport.Jobs -> api.exportJobs()
            DatabaseExport.Customers -> api.exportCustomers()
            DatabaseExport.Invoices -> api.exportInvoices()
            DatabaseExport.MyData -> api.exportMyData()
        }
        body.use { response ->
            response.byteStream().use { input ->
                val output = java.io.ByteArrayOutputStream(); val buffer = ByteArray(8192)
                while(true) {
                    kotlin.coroutines.coroutineContext.ensureActive()
                    val count = input.read(buffer); if(count < 0) break
                    check(output.size() + count <= 50_000_000) { "The export exceeds the supported file size." }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
        }
    }

    fun setExportBusy(kind: DatabaseExport?, info: String? = null) = mutable.update { it.copy(exportBusy = kind, exportInfo = info) }

    fun selectTarget(target: String) {
        if(target !in listOf("watch", "shoe", "mobile")) return
        mutable.update { it.copy(target = target, importResult = null, importError = null) }
    }
    fun setSheetName(value: String) = mutable.update { it.copy(sheetName = value.take(100)) }

    /** Read the document-picker result into memory and count its rows for the preview. */
    fun pick(context: Context, uri: Uri) {
        viewModelScope.launch {
            try {
                val (name, bytes) = withContext(Dispatchers.IO) {
                    var display = "import.csv"; var size = -1L
                    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                        if(c.moveToFirst()) { c.getString(0)?.let { display = it }; size = c.getLong(1) }
                    }
                    check(size <= IMPORT_MAX_BYTES) { "That file is too large to import (25 MB maximum)." }
                    val data = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: throw java.io.IOException("The chosen file cannot be read.")
                    check(data.size <= IMPORT_MAX_BYTES) { "That file is too large to import (25 MB maximum)." }
                    display to data
                }
                choose(name, bytes)
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(importError = e.userMessage()) } }
        }
    }

    fun choose(name: String, bytes: ByteArray) {
        val excel = name.substringAfterLast('.', "").lowercase() in listOf("xlsx", "xls", "xlsm")
        mutable.update { it.copy(picked = PickedImport(name, bytes, if(excel) -1 else countCsvRows(bytes), excel), importResult = null, importError = null) }
    }

    fun clearPicked() = mutable.update { it.copy(picked = null, importResult = null, importError = null) }

    /** Dry run validates only; a real run writes records. The UI confirms before calling with dryRun = false. */
    fun runImport(dryRun: Boolean) {
        val current = state.value
        val file = current.picked ?: return
        if(!TokenStore.canManageInvoices() || current.importBusy) return
        mutable.update { it.copy(importBusy = true, importError = null, importResult = null) }
        viewModelScope.launch {
            try {
                val mediaType = (if(file.isExcel) "application/octet-stream" else "text/csv").toMediaType()
                val part = MultipartBody.Part.createFormData("file", file.name, file.bytes.toRequestBody(mediaType))
                val result = api.importCsv(part, current.target, dryRun, current.sheetName.trim().ifBlank { null })
                mutable.update { it.copy(importBusy = false, importResult = result, picked = if(dryRun) it.picked else null) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val message = if(e is retrofit2.HttpException && e.code() == 429) "Too many import attempts. Try again in a minute." else e.userMessage()
                mutable.update { it.copy(importBusy = false, importError = message) }
            }
        }
    }
}
