package au.mainspring.nativeapp

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.lifecycle.*
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.HttpUrl.Companion.toHttpUrl

data class QuoteSignatureState(val loading: Boolean = false, val quote: MobileQuote? = null, val bitmap: Bitmap? = null, val error: String? = null)
class QuoteSignatureViewModel(private val jobId: String, private val quoteId: String) : ViewModel() {
    private val api = ApiClient.api
    private val origin = ApiClient.getEffectiveBaseUrl().toHttpUrl()
    private val mutable = MutableStateFlow(QuoteSignatureState())
    val state = mutable.asStateFlow()
    init { load() }
    fun load() {
        if(state.value.loading) return
        if(!TokenStore.canWorkJobs()) { mutable.update { it.copy(error = "A technician or manager is required to view customer signatures.") }; return }
        mutable.update { it.copy(loading = true, error = null, bitmap = null) }
        viewModelScope.launch {
            try {
                val quote = api.mobileQuotes(jobId).find { it.id == quoteId } ?: error("This quote is not on the selected job.")
                mutable.update { it.copy(quote = quote) }
                require(quote.hasSignature) { "No customer signature is recorded for this quote." }
                val bitmap = withContext(Dispatchers.IO) {
                    val bytes = api.quoteSignature(quoteId).use { response -> response.byteStream().use { input ->
                        val output = java.io.ByteArrayOutputStream(); val buffer = ByteArray(8192)
                        while(true) {
                            coroutineContext.ensureActive()
                            val size = input.read(buffer); if(size < 0) break
                            require(output.size() + size <= 2_000_000) { "The signature image exceeds the supported file size." }
                            output.write(buffer, 0, size)
                        }
                        output.toByteArray()
                    } }
                    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
                    require(bounds.outWidth in 1..12000 && bounds.outHeight in 1..12000) { "The signature image could not be read." }
                    var sample = 1
                    while(maxOf(bounds.outWidth, bounds.outHeight) / sample > 1600) sample *= 2
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample }) ?: error("The signature image could not be read.")
                }
                mutable.update { it.copy(loading = false, quote = quote, bitmap = bitmap) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                val destination = (e as? retrofit2.HttpException)?.response()?.raw()?.request?.url
                val storageFailure = destination != null && (destination.host != origin.host || destination.port != origin.port || destination.scheme != origin.scheme)
                mutable.update { it.copy(loading = false, error = if(storageFailure) "The signature download link could not be read. Refresh the signature." else e.userMessage()) }
            }
        }
    }
    companion object { fun factory(jobId: String, quoteId: String) = object: ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST") override fun <T: ViewModel> create(modelClass: Class<T>) = QuoteSignatureViewModel(jobId, quoteId) as T
    } }
}
