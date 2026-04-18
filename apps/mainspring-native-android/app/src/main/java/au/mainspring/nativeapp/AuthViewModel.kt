package au.mainspring.nativeapp

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.ApiClient
import au.mainspring.nativeapp.api.LoginRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AuthUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val loggedIn: Boolean = false,
    val sessionSummary: String? = null,
)

class AuthViewModel(application: Application) : AndroidViewModel(application) {

    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state.asStateFlow()

    init {
        val token = TokenStore.getAccessToken()
        if (token != null) {
            viewModelScope.launch { loadSessionOrClear() }
        }
    }

    fun login(tenantSlug: String, email: String, password: String) {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val t = ApiClient.api.login(
                    LoginRequest(
                        tenantSlug = tenantSlug.trim(),
                        email = email.trim(),
                        password = password,
                    ),
                )
                TokenStore.saveTokens(t.accessToken, t.refreshToken)
                loadSessionOrClear()
            } catch (e: Exception) {
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
        val token = TokenStore.getAccessToken() ?: run {
            _state.update { it.copy(loading = false, loggedIn = false, sessionSummary = null) }
            return
        }
        try {
            val s = ApiClient.api.session("Bearer $token")
            _state.update {
                it.copy(
                    loading = false,
                    error = null,
                    loggedIn = true,
                    sessionSummary = "${s.user.fullName} · @${s.tenantSlug} · ${s.planCode}",
                )
            }
        } catch (_: Exception) {
            TokenStore.clear()
            _state.update {
                it.copy(
                    loading = false,
                    error = "Session expired or API unreachable. Sign in again.",
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
