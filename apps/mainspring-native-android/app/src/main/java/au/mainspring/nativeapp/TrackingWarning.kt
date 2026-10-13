package au.mainspring.nativeapp

fun trackingWarning(reason: String?): String? = when(reason) {
    null, "" -> null
    "no_phone" -> "Tracking SMS was not sent: this customer has no phone number."
    "sms_not_configured" -> "Tracking SMS was not sent: SMS is not configured for this shop."
    else -> "Tracking SMS could not be sent. Check the job before sending its tracking link manually."
}
