package au.mainspring.nativeapp

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

const val ORDER_IMPORT_MAX_BYTES = 10 * 1024 * 1024

data class OrderImportState(
    val picked: PickedImport? = null,
    val sheets: List<String> = emptyList(),
    val sheet: String? = null,
    val busy: Boolean = false,
    val result: CustomerOrderImportResult? = null,
    val error: String? = null,
)

/** Imports customer orders from CSV/Excel: pick a file, dry run, then confirm. The server caps uploads at 10 MB. */
class OrderImportViewModel(private val api: OwnerAdminApi = ApiClient.service(OwnerAdminApi::class.java)) : ViewModel() {
    private val mutable = MutableStateFlow(OrderImportState())
    val state = mutable.asStateFlow()

    private fun part(file: PickedImport): MultipartBody.Part {
        val type = (if(file.isExcel) "application/octet-stream" else "text/csv").toMediaType()
        return MultipartBody.Part.createFormData("file", file.name, file.bytes.toRequestBody(type))
    }

    fun pick(context: Context, uri: Uri) {
        viewModelScope.launch {
            try {
                val (name, bytes) = withContext(Dispatchers.IO) {
                    var display = "orders.csv"; var size = -1L
                    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                        if(c.moveToFirst()) { c.getString(0)?.let { display = it }; size = c.getLong(1) }
                    }
                    check(size <= ORDER_IMPORT_MAX_BYTES) { "That file is too large to import (10 MB maximum)." }
                    val data = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: throw java.io.IOException("The chosen file cannot be read.")
                    check(data.size <= ORDER_IMPORT_MAX_BYTES) { "That file is too large to import (10 MB maximum)." }
                    display to data
                }
                choose(name, bytes)
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
        }
    }

    /** Holds the file and, for Excel, asks the server for its sheet names so one can be picked. */
    fun choose(name: String, bytes: ByteArray) {
        val excel = name.substringAfterLast('.', "").lowercase() in listOf("xlsx", "xls", "xlsm")
        val file = PickedImport(name, bytes, if(excel) -1 else countCsvRows(bytes), excel)
        mutable.update { OrderImportState(picked = file) }
        if(!excel) return
        viewModelScope.launch {
            try {
                val sheets = api.orderImportSheets(part(file))
                mutable.update { it.copy(sheets = sheets, sheet = sheets.firstOrNull()) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
        }
    }

    fun selectSheet(name: String) = mutable.update { it.copy(sheet = name, result = null) }
    fun reset() = mutable.update { OrderImportState() }

    /** A dry run validates only; the UI confirms before calling with dryRun = false. */
    fun run(dryRun: Boolean, onImported: () -> Unit = {}) {
        val current = state.value
        val file = current.picked ?: return
        if(current.busy) return
        mutable.update { it.copy(busy = true, error = null, result = null) }
        viewModelScope.launch {
            try {
                val result = api.importCustomerOrders(part(file), dryRun, current.sheet)
                mutable.update { it.copy(busy = false, result = result, picked = if(dryRun) it.picked else null) }
                if(!dryRun) onImported()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(busy = false, error = e.userMessage()) } }
        }
    }
}
