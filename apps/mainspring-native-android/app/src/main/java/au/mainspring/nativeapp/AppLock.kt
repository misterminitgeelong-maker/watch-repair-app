package au.mainspring.nativeapp

import android.content.Context
import android.os.Build
import android.os.SystemClock
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Optional unlock when the app opens (fingerprint, face, or the phone's PIN/pattern as the fallback).
 * It only ever asks the phone to confirm the person; it never asks for, stores or checks the shop password.
 * The signed-in session is untouched: locking just covers the screen until the phone says it is the owner.
 */
object AppLock {
    private const val FILE = "mainspring_app_lock"
    private const val K_ON = "enabled"
    /** Time in the background before the app locks again; short switches (e.g. to the phone app to call) do not re-ask. */
    const val GRACE_MS = 30_000L

    private val lockedFlow = MutableStateFlow(false)
    val locked: StateFlow<Boolean> = lockedFlow.asStateFlow()
    private var backgroundedAt = 0L
    private fun prefs() = TokenStore.context()?.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun enabled(): Boolean = prefs()?.getBoolean(K_ON, false) ?: false
    fun setEnabled(value: Boolean) { prefs()?.edit()?.putBoolean(K_ON, value)?.apply(); if(!value) lockedFlow.value = false }

    /** Cold start: locked right away when the setting is on. */
    fun onColdStart() { lockedFlow.value = enabled() }
    fun onBackground(now: Long = SystemClock.elapsedRealtime()) { backgroundedAt = now }
    fun onForeground(now: Long = SystemClock.elapsedRealtime()) { if(shouldRelock(enabled(), backgroundedAt, now)) lockedFlow.value = true }
    fun unlocked() { lockedFlow.value = false }

    /** Pure rule so it can be unit tested: lock again once the app has been away longer than [GRACE_MS]. */
    internal fun shouldRelock(enabled: Boolean, backgroundedAt: Long, now: Long): Boolean = enabled && backgroundedAt > 0L && now - backgroundedAt > GRACE_MS

    /** Biometric where available, always with the phone's PIN/pattern/password as the fallback. */
    internal fun authenticators(sdk: Int = Build.VERSION.SDK_INT): Int =
        if(sdk >= Build.VERSION_CODES.R) BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
        else BiometricManager.Authenticators.BIOMETRIC_WEAK or BiometricManager.Authenticators.DEVICE_CREDENTIAL

    /** True when the phone has a screen lock or enrolled biometric to unlock with. */
    fun available(context: Context): Boolean = try {
        BiometricManager.from(context).canAuthenticate(authenticators()) == BiometricManager.BIOMETRIC_SUCCESS
    } catch(_: Exception) { false }

    fun prompt(activity: FragmentActivity, title: String, onSuccess: () -> Unit, onFailure: (String) -> Unit = {}) {
        val callback = object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) { onSuccess() }
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) { onFailure(errString.toString()) }
        }
        val info = BiometricPrompt.PromptInfo.Builder().setTitle(title).setSubtitle("Use your fingerprint, face or phone PIN")
            .setAllowedAuthenticators(authenticators()).build()
        BiometricPrompt(activity, ContextCompat.getMainExecutor(activity), callback).authenticate(info)
    }
}
