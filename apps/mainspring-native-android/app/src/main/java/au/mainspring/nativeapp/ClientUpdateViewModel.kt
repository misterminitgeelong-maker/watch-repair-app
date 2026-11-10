package au.mainspring.nativeapp

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import com.google.gson.annotations.SerializedName
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import retrofit2.http.GET

data class AndroidClientConfig(@SerializedName("minimum_version_code") val minimum: Int = 0,
    @SerializedName("update_message") val message: String? = null, @SerializedName("sentry_dsn") val sentryDsn: String? = null)
interface ClientConfigApi { @GET("v1/client-config/android") suspend fun config(): AndroidClientConfig }
fun requiresNativeUpdate(minimum: Int, installed: Int): Boolean = minimum > 0 && installed < minimum

class ClientUpdateViewModel(app: Application): AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("native-client-config", Application.MODE_PRIVATE)
    private val mutable = MutableStateFlow(AndroidClientConfig(prefs.getInt("minimum", 0), prefs.getString("update-message", null)))
    val state = mutable.asStateFlow()
    private var loading = false
    fun refresh() {
        if(loading || BuildConfig.DEBUG) return
        loading = true
        viewModelScope.launch {
            try {
                val config = ApiClient.service(ClientConfigApi::class.java).config()
                mutable.value = config
                prefs.edit().putInt("minimum", config.minimum).putString("update-message", config.message).apply()
                NativeDiagnostics.start(getApplication(), config.sentryDsn)
            } catch(e: CancellationException) { throw e } catch(_: Exception) { /* Last verified policy remains available offline. */ }
            finally { loading = false }
        }
    }
}
