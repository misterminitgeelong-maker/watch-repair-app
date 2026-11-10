package au.mainspring.nativeapp

import android.app.Application
import io.sentry.Sentry
import io.sentry.android.core.SentryAndroid

class MainspringApplication : Application() {
    override fun onCreate() { super.onCreate(); NativeDiagnostics.start(this) }
}

object NativeDiagnostics {
    private var configuredDsn: String? = null
    fun start(app: Application, serverDsn: String? = null) {
        if(BuildConfig.DEBUG) return
        val prefs = app.getSharedPreferences("native-client-config", Application.MODE_PRIVATE)
        val dsn = serverDsn?.takeIf { it.isNotBlank() } ?: BuildConfig.SENTRY_DSN.takeIf { it.isNotBlank() } ?: prefs.getString("sentry-dsn", null) ?: return
        if(configuredDsn == dsn) return
        val uri = runCatching { java.net.URI(dsn) }.getOrNull() ?: return
        if(uri.scheme != "https" || uri.host.isNullOrBlank() || uri.userInfo.isNullOrBlank() || uri.userInfo.contains(':')) return
        try {
            SentryAndroid.init(app) { options ->
                options.dsn = dsn
                options.release = "au.mainspring.app@${BuildConfig.VERSION_NAME}+${BuildConfig.VERSION_CODE}"
                options.environment = "production"
                options.isSendDefaultPii = false
                options.isAttachScreenshot = false
                options.isAttachViewHierarchy = false
                options.isEnableUserInteractionBreadcrumbs = false
                options.isEnableActivityLifecycleBreadcrumbs = false
                options.tracesSampleRate = 0.0
                options.setTag("component", "native-android")
                options.setBeforeSend { event, _ ->
                    event.user = null
                    event.request = null
                    event.message = null
                    event.breadcrumbs?.clear()
                    event.extras?.clear()
                    event.exceptions?.forEach { it.value = null }
                    event
                }
            }
            configuredDsn = dsn
            prefs.edit().putString("sentry-dsn", dsn).apply()
        } catch(_: Exception) { /* Diagnostics must never prevent the app from starting. */ }
    }
}
