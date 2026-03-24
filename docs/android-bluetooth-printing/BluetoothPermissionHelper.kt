package com.mainspring.print

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.result.ActivityResultLauncher
import androidx.core.content.ContextCompat

object BluetoothPermissionHelper {

    fun requiredPermissions(): Array<String> {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_SCAN
            )
        } else {
            emptyArray()
        }
    }

    fun hasRequiredPermissions(activity: Activity): Boolean {
        val required = requiredPermissions()
        if (required.isEmpty()) return true

        return required.all { permission ->
            ContextCompat.checkSelfPermission(activity, permission) == PackageManager.PERMISSION_GRANTED
        }
    }

    fun requestIfNeeded(
        activity: Activity,
        launcher: ActivityResultLauncher<Array<String>>
    ) {
        if (!hasRequiredPermissions(activity)) {
            launcher.launch(requiredPermissions())
        }
    }
}
