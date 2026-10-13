package au.mainspring.nativeapp.ui

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class AppAppearance(val label: String) {
    WARM("Refined Warmth"), NIGHT("Night Workshop"), STEEL("Steel & Amber"), MINIT("Mister Minit")
}

/** Device appearance only. Entitlements and shop configuration remain server-owned. */
object DesignPreferences {
    private var preferences: android.content.SharedPreferences? = null
    private val selected = MutableStateFlow(AppAppearance.WARM)
    val appearance = selected.asStateFlow()
    private val field = MutableStateFlow(false)
    val fieldNavigation = field.asStateFlow()
    fun init(context: Context) {
        if(preferences != null) return
        preferences = context.applicationContext.getSharedPreferences("mainspring_appearance", Context.MODE_PRIVATE)
        field.value = preferences?.getBoolean("field_navigation",false) ?: false
        selected.value = AppAppearance.entries.firstOrNull { it.name == preferences?.getString("appearance", null) } ?: AppAppearance.WARM
    }
    fun fieldNavigation(value: Boolean) {field.value=value;preferences?.edit()?.putBoolean("field_navigation",value)?.apply()}
    fun select(value: AppAppearance) {
        selected.value = value
        preferences?.edit()?.putString("appearance", value.name)?.apply()
    }
}
