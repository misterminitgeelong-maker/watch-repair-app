package au.mainspring.nativeapp

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

/** Receives push messages. When the app is closed Android shows the notification itself; this shows it while the app is open. */
class PushService : FirebaseMessagingService() {
    override fun onNewToken(token: String) { PushRegistration.onNewToken(applicationContext, token) }

    override fun onMessageReceived(message: RemoteMessage) {
        val title = message.notification?.title ?: return
        val body = message.notification?.body.orEmpty()
        PushNotifications.show(applicationContext, title, body, message.data["path"])
    }
}

object PushNotifications {
    const val CHANNEL_ID = "mainspring_alerts"
    const val EXTRA_PATH = "path"

    fun ensureChannel(context: Context) {
        if(Build.VERSION.SDK_INT < 26) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID, "Shop alerts", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Quote approvals and declines, paid invoices, customer replies and new leads"
        })
    }

    fun show(context: Context, title: String, body: String, path: String?) {
        if(!PushRegistration.permitted(context)) return
        ensureChannel(context)
        val open = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            path?.let { putExtra(EXTRA_PATH, it) }
        }
        val id = (path ?: title).hashCode()
        val pending = PendingIntent.getActivity(context, id, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = NotificationCompat.Builder(context, CHANNEL_ID).setSmallIcon(R.drawable.ic_stat_mainspring)
            .setContentTitle(title).setContentText(body).setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(pending).setAutoCancel(true).setPriority(NotificationCompat.PRIORITY_HIGH).build()
        try { NotificationManagerCompat.from(context).notify(id, notification) } catch(_: SecurityException) {}
    }
}
