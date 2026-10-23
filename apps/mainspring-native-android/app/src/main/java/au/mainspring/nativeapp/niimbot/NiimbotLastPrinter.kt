package au.mainspring.nativeapp.niimbot

import android.content.Context

/** Minimal key/value seam so the remember-last-printer logic is unit-testable without Android. */
interface NiimbotKeyValueStore {
    fun get(key: String): String?
    fun put(key: String, value: String?)
}

private class PrefsStore(context: Context) : NiimbotKeyValueStore {
    private val prefs = context.applicationContext.getSharedPreferences("niimbot_printer", Context.MODE_PRIVATE)
    override fun get(key: String): String? = prefs.getString(key, null)
    override fun put(key: String, value: String?) { prefs.edit().apply { if (value == null) remove(key) else putString(key, value) }.apply() }
}

/** Remembers the last printer that printed successfully so the next print can connect without a scan (web: auto-connect). */
class NiimbotLastPrinter(private val store: NiimbotKeyValueStore) {
    constructor(context: Context) : this(PrefsStore(context))

    fun load(): NiimbotDevice? {
        val address = store.get(KEY_ADDRESS)?.takeIf { isValidAddress(it) } ?: return null
        return NiimbotDevice(store.get(KEY_NAME)?.takeIf { it.isNotBlank() } ?: "Niimbot printer", address)
    }

    fun save(device: NiimbotDevice) {
        if (!isValidAddress(device.address)) return
        store.put(KEY_ADDRESS, device.address); store.put(KEY_NAME, device.name)
    }

    fun forget() { store.put(KEY_ADDRESS, null); store.put(KEY_NAME, null) }

    companion object {
        private const val KEY_ADDRESS = "last_address"
        private const val KEY_NAME = "last_name"
        private val MAC = Regex("^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")
        fun isValidAddress(address: String): Boolean = MAC.matches(address)
    }
}
