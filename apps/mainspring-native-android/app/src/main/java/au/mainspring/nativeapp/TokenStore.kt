package au.mainspring.nativeapp

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

object TokenStore {
    private const val FILE = "mainspring_native_tokens"
    private const val K_ACCESS = "access_token"
    private const val K_REFRESH = "refresh_token"
    private const val K_BASE_URL = "custom_api_base_url"
    private const val K_GENERATION = "session_generation"
    private val expired = MutableSharedFlow<Long>(extraBufferCapacity = 1)
    val expiredSessions = expired.asSharedFlow()
    data class SessionSnapshot(val generation: Long, val access: String?, val refresh: String?)
    @Synchronized fun sessionSnapshot() = SessionSnapshot(sessionGeneration(), getAccessToken(), getRefreshToken())
    fun sessionGeneration(): Long = if(::prefs.isInitialized) prefs.getLong(K_GENERATION, 0) else 0

    private lateinit var prefs: android.content.SharedPreferences
    private lateinit var appContext: Context

    fun init(context: Context) {
        if (::prefs.isInitialized) return
        appContext = context.applicationContext
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

    fun getApiBaseUrl(): String? = prefs.getString(K_BASE_URL, null)?.takeIf { it.isNotBlank() }

    @Synchronized fun saveApiBaseUrl(url: String?) {
        val previous = (getApiBaseUrl() ?: BuildConfig.API_BASE_URL).trimEnd('/')
        val next = (url?.takeIf { it.isNotBlank() } ?: BuildConfig.API_BASE_URL).trim().trimEnd('/')
        if(previous != next) clearTokens()
        prefs.edit().apply {
            if (url.isNullOrBlank()) remove(K_BASE_URL)
            else putString(K_BASE_URL, url.trim())
        }.apply()
    }

    @Synchronized fun saveTokens(access: String, refresh: String?) {
        prefs.edit()
            .putLong(K_GENERATION, sessionGeneration() + 1)
            .putString(K_ACCESS, access)
            .apply {
                if (refresh != null) putString(K_REFRESH, refresh)
                else remove(K_REFRESH)
            }
            .apply()
    }

    @Synchronized fun clear() {
        au.mainspring.nativeapp.data.QuoteNavCache.clear()
        val next = sessionGeneration() + 1
        prefs.edit().clear().putLong(K_GENERATION, next).apply()
        // The offline write queue lives in these prefs, so it is already wiped; reset its in-memory view.
        au.mainspring.nativeapp.offline.OfflineSync.onSessionCleared()
        cleanupUnusedOwnedPhotos()
    }
    internal fun context(): Context? = if(::appContext.isInitialized) appContext else null
    internal fun referencesPhoto(uri: String): Boolean = prefs.all.values.any { it is String && it.contains(uri) }
    @Synchronized fun clearTokens() { prefs.edit().remove(K_ACCESS).remove(K_REFRESH).remove("session_cache").putLong(K_GENERATION, sessionGeneration() + 1).apply() }
    /** Last good session summary (features, role, sites...), so the app can open with no signal. Not a credential: the tokens stay separate. */
    fun saveSessionCache(json: String?) { if(::prefs.isInitialized) prefs.edit().apply { if(json == null) remove("session_cache") else putString("session_cache", json) }.apply() }
    fun sessionCache(): String? = if(::prefs.isInitialized) prefs.getString("session_cache", null)?.takeIf { it.isNotBlank() } else null
    @Synchronized fun expireSession(expectedGeneration: Long): Boolean {
        if(sessionGeneration() != expectedGeneration) return false
        clearTokens(); expired.tryEmit(sessionGeneration()); return true
    }
    @Synchronized fun saveRefreshedTokens(access: String, refresh: String?, expectedGeneration: Long): Boolean {
        if(sessionGeneration() != expectedGeneration) return false
        prefs.edit().putString(K_ACCESS, access).apply { if(refresh == null) remove(K_REFRESH) else putString(K_REFRESH, refresh) }.apply()
        return true
    }

    fun setDraftScope(tenantId: String, userId: String) {
        prefs.edit().putString("draft_scope", "${getApiBaseUrl() ?: BuildConfig.API_BASE_URL}|$tenantId|$userId").putString("tenant_id", tenantId).apply()
    }
    /** Scope an offline write is bound to (api base | tenant | user), or null when no verified session exists. */
    fun offlineScope(): String? = if(::prefs.isInitialized) prefs.getString("draft_scope", null) else null
    fun hasOfflineStorage(): Boolean = ::prefs.isInitialized
    fun loadOfflineQueue(): String? = if(::prefs.isInitialized) prefs.getString("offline_write_queue", null) else null
    @android.annotation.SuppressLint("ApplySharedPref")
    fun saveOfflineQueue(json: String?) { if(::prefs.isInitialized) prefs.edit().apply { if(json == null) remove("offline_write_queue") else putString("offline_write_queue", json) }.commit() }
    fun loadScopedString(key: String): String? = if(::prefs.isInitialized) prefs.getString(key, null) else null
    fun saveScopedString(key: String, value: String) { if(::prefs.isInitialized) prefs.edit().putString(key, value).apply() }
    fun currentTenantId(): String = prefs.getString("tenant_id", "").orEmpty()
    /** Wait for prior async draft writes before an intake POST can commit on the server. */
    fun flushDraftCheckpoint() { check(prefs.edit().commit()) { "Could not retain the intake checkpoint on this device. Free storage before submitting." } }
    private fun draftKey(): String? = prefs.getString("draft_scope", null)?.let { "watch_intake:$it" }
    fun loadIntakeDraft(): String? = draftKey()?.let { prefs.getString(it, null) }
    fun saveIntakeDraft(json: String) { draftKey()?.let { prefs.edit().putString(it, json).apply() } }
    fun clearIntakeDraft() { draftKey()?.let { prefs.edit().remove(it).apply() } }
    fun loadShoeDraft(): String? = draftKey()?.let { prefs.getString("shoe:$it", null) }
    fun saveShoeDraft(json: String) { draftKey()?.let { prefs.edit().putString("shoe:$it", json).apply() } }
    fun clearShoeDraft() { draftKey()?.let { prefs.edit().remove("shoe:$it").apply() } }
    fun loadMobileDraft(): String? = draftKey()?.let { prefs.getString("mobile:$it", null) }
    fun saveMobileDraft(json: String) { draftKey()?.let { prefs.edit().putString("mobile:$it", json).apply() } }
    fun clearMobileDraft() { draftKey()?.let { prefs.edit().remove("mobile:$it").apply() } }
    fun setShopIdentity(currency: String?,name: String?,abn: String?,phone: String?,address: String?) {
        prefs.edit().putString("shop_currency",currency).putString("shop_name",name).putString("shop_abn",abn).putString("shop_phone",phone).putString("shop_address",address).apply()
    }
    /** User id of the signed-in account, taken from the draft scope (`base|tenant|user`). */
    fun currentUserId(): String = if(::prefs.isInitialized) prefs.getString("draft_scope", null)?.substringAfterLast('|', "").orEmpty() else ""
    fun shopValue(key: String): String? = if(::prefs.isInitialized) prefs.getString("shop_$key",null) else null
    fun setCalendarTimezone(zone: String) { prefs.edit().putString("calendar_zone", zone).apply() }
    fun calendarTimezone(): String = if(::prefs.isInitialized) prefs.getString("calendar_zone", "Australia/Sydney") ?: "Australia/Sydney" else "Australia/Sydney"
    /** Push device token, if one was ever registered; removed server-side at sign-out and cleared with [clear]. */
    fun deviceToken(): String? = if(::prefs.isInitialized) prefs.getString("device_push_token", null)?.takeIf { it.isNotBlank() } else null
    fun saveDeviceToken(token: String?) { prefs.edit().apply { if(token.isNullOrBlank()) remove("device_push_token") else putString("device_push_token", token) }.apply() }
    fun isOwner(): Boolean = prefs.getString("session_role", null) == "owner"
    fun setSessionRole(role: String) { prefs.edit().putString("session_role", role).apply() }
    fun canManageTeam(): Boolean = prefs.getString("session_role", null) in listOf("owner", "platform_admin")
    fun canManageInvoices(): Boolean = prefs.getString("session_role", null) in listOf("owner", "manager", "platform_admin")
    fun canWorkJobs(): Boolean = prefs.getString("session_role", null) in listOf("owner", "manager", "tech", "platform_admin")
    fun loadMessageDraft(key: String): String = draftKey()?.let { prefs.getString("message:$it:$key", "") }.orEmpty()
    fun saveMessageDraft(key: String, body: String) { draftKey()?.let { prefs.edit().putString("message:$it:$key", body).apply() } }
    fun pendingOperation(key: String): Boolean = draftKey()?.let { prefs.getBoolean("pending:$it:$key", false) } ?: false
    fun setPendingOperation(key: String, pending: Boolean) { draftKey()?.let { prefs.edit().putBoolean("pending:$it:$key", pending).commit() } }

    /** Captures the verified account and sign-in so delayed callbacks cannot write into a newer account. */
    @Synchronized fun bindDrafts() = BoundDrafts(draftKey(), sessionGeneration())
    class BoundDrafts internal constructor(private val scope: String?, private val generation: Long) {
        private fun read(key: String?): String? = synchronized(TokenStore) { if(key == null || sessionGeneration() != generation) null else prefs.getString(key, null) }
        private fun write(key: String?, value: String?) = synchronized(TokenStore) {
            if(key != null && sessionGeneration() == generation) prefs.edit().apply { if(value == null) remove(key) else putString(key,value) }.apply()
        }
        fun loadIntakeDraft() = read(scope)
        fun saveIntakeDraft(json: String) = write(scope,json)
        fun clearIntakeDraft() = write(scope,null)
        fun loadShoeDraft() = read(scope?.let { "shoe:$it" })
        fun saveShoeDraft(json: String) = write(scope?.let { "shoe:$it" },json)
        fun clearShoeDraft() = write(scope?.let { "shoe:$it" },null)
        fun loadMobileDraft() = read(scope?.let { "mobile:$it" })
        fun saveMobileDraft(json: String) = write(scope?.let { "mobile:$it" },json)
        fun clearMobileDraft() = write(scope?.let { "mobile:$it" },null)
        fun loadMessageDraft(key: String) = read(scope?.let { "message:$it:$key" }).orEmpty()
        fun saveMessageDraft(key: String, json: String) = write(scope?.let { "message:$it:$key" },json)
        fun pendingOperation(key: String): Boolean = synchronized(TokenStore) { scope != null && sessionGeneration() == generation && prefs.getBoolean("pending:$scope:$key",false) }
        // This checkpoint must reach disk before the server can acknowledge a write.
        @android.annotation.SuppressLint("ApplySharedPref")
        fun setPendingOperation(key: String, value: Boolean) = synchronized(TokenStore) { if(scope != null && sessionGeneration() == generation) prefs.edit().putBoolean("pending:$scope:$key",value).commit() else false }
    }
}
