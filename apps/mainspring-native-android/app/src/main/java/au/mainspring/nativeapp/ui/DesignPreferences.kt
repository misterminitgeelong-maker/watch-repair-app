package au.mainspring.nativeapp.ui

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

enum class AppAppearance(val label: String) {
    MAINSPRING("Mainspring"), CALIBRE("Calibre"), WARM("Atelier"), NIGHT("Night Workshop"), STEEL("Steel & Amber"), MINIT("Mister Minit")
}

/** The one appearance the app ships with. Older stored choices (Calibre, Atelier, Night, Steel, Minit) are ignored and cleared. */
val DEFAULT_APPEARANCE = AppAppearance.MAINSPRING

/** Device appearance only. Entitlements and shop configuration remain server-owned. */
object DesignPreferences {
    private var preferences: android.content.SharedPreferences? = null
    private val selected = MutableStateFlow(DEFAULT_APPEARANCE)
    val appearance = selected.asStateFlow()
    private val field = MutableStateFlow(false)
    val fieldNavigation = field.asStateFlow()
    fun init(context: Context) {
        if(preferences != null) return
        preferences = context.applicationContext.getSharedPreferences("mainspring_appearance", Context.MODE_PRIVATE)
        field.value = preferences?.getBoolean("field_navigation",false) ?: false
        selected.value = DEFAULT_APPEARANCE
        if(preferences?.contains("appearance") == true) preferences?.edit()?.remove("appearance")?.apply()
    }
    fun fieldNavigation(value: Boolean) {field.value=value;preferences?.edit()?.putBoolean("field_navigation",value)?.apply()}
    fun select(value: AppAppearance) {
        selected.value = value
        preferences?.edit()?.putString("appearance", value.name)?.apply()
    }
}
