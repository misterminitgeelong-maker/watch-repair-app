package au.mainspring.nativeapp

/**
 * Remembered Shop ID for the sign-in form. Deliberately separate from [TokenStore] (which is wiped on sign-out)
 * so the shop ID survives signing out, like the web app's "remember" behaviour. A shop ID is not a secret.
 */
object LoginPrefs {
    private const val FILE = "mainspring_login_prefs"
    private const val K_SHOP = "remembered_shop_id"
    private const val K_REMEMBER = "remember_shop_id"
    private fun prefs() = TokenStore.context()?.getSharedPreferences(FILE, android.content.Context.MODE_PRIVATE)

    /** Whether the checkbox is on; defaults to on until the user turns it off. */
    fun rememberEnabled(): Boolean = prefs()?.getBoolean(K_REMEMBER, true) ?: true
    fun rememberedShopId(): String = if(rememberEnabled()) prefs()?.getString(K_SHOP, null).orEmpty() else ""
    private const val K_EMAIL = "last_email"
    /** Email used for the last sign-in (not a secret); offered again only on the "Welcome back" prompt. */
    fun lastEmail(): String = if(rememberEnabled()) prefs()?.getString(K_EMAIL, null).orEmpty() else ""
    fun saveEmail(email: String) { if(rememberEnabled()) prefs()?.edit()?.putString(K_EMAIL, email.trim())?.apply() }
    fun save(shopId: String, remember: Boolean) {
        val p = prefs() ?: return
        p.edit().putBoolean(K_REMEMBER, remember).apply { if(remember) putString(K_SHOP, shopId.trim()) else remove(K_SHOP) }.apply()
    }
}
