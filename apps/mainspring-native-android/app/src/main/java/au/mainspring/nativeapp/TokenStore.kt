package au.mainspring.nativeapp

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

object TokenStore {
    private const val FILE = "mainspring_native_tokens"
    private const val K_ACCESS = "access_token"
    private const val K_REFRESH = "refresh_token"

    private lateinit var prefs: android.content.SharedPreferences

    fun init(context: Context) {
        if (::prefs.isInitialized) return
        val master = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        prefs = EncryptedSharedPreferences.create(
            context,
            FILE,
            master,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    fun getAccessToken(): String? = prefs.getString(K_ACCESS, null)?.takeIf { it.isNotBlank() }

    fun getRefreshToken(): String? = prefs.getString(K_REFRESH, null)?.takeIf { it.isNotBlank() }

    fun saveTokens(access: String, refresh: String?) {
        prefs.edit()
            .putString(K_ACCESS, access)
            .apply {
                if (refresh != null) putString(K_REFRESH, refresh)
                else remove(K_REFRESH)
            }
            .apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }
}
