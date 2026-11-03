package au.mainspring.nativeapp

/** The two things push registration needs from the outside, so the rules can be tested without a phone. */
interface DeviceRegistryApi { suspend fun register(token: String) }
interface DeviceTokenStore { fun get(): String?; fun save(token: String?) }

/**
 * Keeps this phone's push token registered with the server for the signed-in user.
 * Registers only when signed in and notifications are allowed; remembers the token so sign-out can remove it.
 */
class DeviceRegistrar(private val api: DeviceRegistryApi, private val store: DeviceTokenStore) {
    /** Returns true when the token was sent to the server. A failed send keeps the old stored token and can be retried. */
    suspend fun sync(token: String?, signedIn: Boolean, permitted: Boolean): Boolean {
        if(token.isNullOrBlank() || !signedIn || !permitted) return false
        return try {
            api.register(token)
            store.save(token)
            true
        } catch(e: kotlinx.coroutines.CancellationException) { throw e }
        catch(_: Exception) { false }
    }
}
