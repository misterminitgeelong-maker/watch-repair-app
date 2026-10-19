package au.mainspring.nativeapp

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Process-wide network state. Call [init] once (e.g. from MainActivity); until then [online] stays true. */
object ConnectivityMonitor {
    private val mutable = MutableStateFlow(true)
    val online: StateFlow<Boolean> = mutable.asStateFlow()
    private var registered = false

    @Synchronized fun init(context: Context) {
        if (registered) return
        val cm = context.applicationContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return
        try {
            val caps = cm.getNetworkCapabilities(cm.activeNetwork)
            mutable.value = caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true
            cm.registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) { mutable.value = true }
                override fun onLost(network: Network) { mutable.value = false }
                override fun onUnavailable() { mutable.value = false }
            })
            registered = true
        } catch (_: SecurityException) {
            mutable.value = true
        }
    }
}
