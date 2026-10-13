package au.mainspring.nativeapp

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.LoginRequest
import au.mainspring.nativeapp.api.MultiSiteLoginRequest
import au.mainspring.nativeapp.api.SiteSwitchRequest
import au.mainspring.nativeapp.api.SessionSite
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

data class AuthUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val loggedIn: Boolean = false,
    val sessionSummary: String? = null,
    val features: Set<String> = emptySet(),
    val sessionKey: String? = null,
    val sites: List<SessionSite> = emptyList(),
    val activeSiteId: String? = null,
    val consoleOnly: Boolean = false,
)

class AuthViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch { TokenStore.expiredSessions.collect { generation ->
            if(TokenStore.sessionGeneration() == generation && TokenStore.getAccessToken() == null) _state.value = AuthUiState(error = "Your session expired. Sign in again; your drafts are retained.")
        } }
        val token = TokenStore.getAccessToken()
        if (token != null) {
            _state.update { it.copy(loading = true) }
            viewModelScope.launch { loadSessionOrClear() }
        }
    }

    fun login(tenantSlug: String, email: String, password: String, serverUrl: String? = null) {
        if (_state.value.loading) return
        val url = (serverUrl?.takeIf { it.isNotBlank() } ?: ApiClient.getEffectiveBaseUrl()).trim()
        val parsed = url.toHttpUrlOrNull()
        if (parsed == null || (parsed.scheme != "https" && !(BuildConfig.DEBUG && parsed.host in listOf("10.0.2.2", "localhost", "127.0.0.1")))) {
            _state.update { it.copy(error = "Use an HTTPS server address.") }; return
        }
        if (!serverUrl.isNullOrBlank()) {
            TokenStore.saveApiBaseUrl(serverUrl)
        }
        _state.update { it.copy(loading = true, error = null) }
        val loginGeneration = TokenStore.sessionGeneration()
        viewModelScope.launch {
            try {
                val t = if(tenantSlug.isBlank()) ApiClient.api.multiSiteLogin(MultiSiteLoginRequest(email.trim(),password)) else ApiClient.api.login(
                    LoginRequest(
                        tenantSlug = tenantSlug.trim(),
                        email = email.trim(),
                        password = password,
                    ),
                )
                if(TokenStore.sessionGeneration() != loginGeneration) return@launch
                TokenStore.saveTokens(t.accessToken, t.refreshToken)
                loadSessionOrClear()
            } catch(e: CancellationException) { throw e
            } catch (e: Exception) {
                if(TokenStore.sessionGeneration() != loginGeneration) return@launch
                _state.update {
                    it.copy(
                        loading = false,
                        error = humanError(e),
                        loggedIn = false,
                        sessionSummary = null,
                    )
                }
            }
        }
    }

    private suspend fun loadSessionOrClear() {
        val generation = TokenStore.sessionGeneration()
        val token = TokenStore.getAccessToken() ?: run {
            _state.update { it.copy(loading = false, loggedIn = false, sessionSummary = null) }
            return
        }
        try {
            val s = ApiClient.api.session()
            if(TokenStore.sessionGeneration() != generation) return
            TokenStore.setDraftScope(s.tenantId, s.user.id)
            TokenStore.setCalendarTimezone(s.calendarTimezone)
            TokenStore.setShopIdentity(s.currency,s.shopName,s.shopAbn,s.shopPhone,s.shopAddress)
            TokenStore.setSessionRole(s.user.role)
            _state.update {
                it.copy(
                    loading = false,
                    error = null,
                    loggedIn = true,
                    sessionSummary = "${s.user.fullName} · @${s.tenantSlug} · ${s.planCode}",
                    features = s.enabledFeatures.toSet(),
                    sessionKey = "${s.tenantId}|${s.user.id}|$generation",
                    sites = s.sites.orEmpty(),
                    activeSiteId = s.activeSiteId ?: s.tenantId,
                    consoleOnly = s.hqConsole || s.platformConsole,
                )
            }
        } catch (e: Exception) {
            if(TokenStore.sessionGeneration() != generation) return
            val expired = e is retrofit2.HttpException && e.code() == 401
            if (expired) TokenStore.clearTokens()
            _state.update {
                it.copy(
                    loading = false,
                    error = if (expired) "Session expired. Sign in again." else "Cannot reach your shop. Check your connection and try again; your saved session is retained.",
                    loggedIn = false,
                    sessionSummary = null,
                )
            }
        }
    }

    fun logout() {
        TokenStore.clear()
        _state.value = AuthUiState()
    }
    fun switchSite(tenantId: String) {
        val snapshot = _state.value
        if(snapshot.loading || !snapshot.loggedIn || snapshot.activeSiteId == tenantId || snapshot.sites.none { it.tenantId == tenantId }) return
        val generation = TokenStore.sessionGeneration()
        val api = ApiClient.api
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val tokens = api.switchSite(SiteSwitchRequest(tenantId))
                if(TokenStore.sessionGeneration() != generation) return@launch
                TokenStore.saveTokens(tokens.accessToken,tokens.refreshToken)
                loadSessionOrClear()
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) {
                if(TokenStore.sessionGeneration() == generation) _state.update { it.copy(loading = false, error = "Could not switch shops. ${e.userMessage()}") }
            }
        }
    }
}

class AuthViewModelFactory(private val application: Application) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(AuthViewModel::class.java)) {
            return AuthViewModel(application) as T
        }
        throw IllegalArgumentException("Unknown ViewModel: ${modelClass.name}")
    }
}

private fun humanError(e: Exception): String {
    val raw = e.message ?: return "Request failed."
    if (raw.contains("401") || raw.contains("Unable to resolve host")) return raw
    if (raw.contains("404")) return "API not found — check API base URL in local.properties (api.base.url)."
    if (raw.contains("Failed to connect")) return "Cannot reach API — check base URL, VPN, and that the server is running."
    return raw
}
