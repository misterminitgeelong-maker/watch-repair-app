package au.mainspring.nativeapp

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AppLockRuleTest {
    @Test fun relocksOnlyAfterTheGracePeriodAndOnlyWhenEnabled() {
        assertFalse(AppLock.shouldRelock(enabled = false, backgroundedAt = 1_000, now = 1_000 + AppLock.GRACE_MS * 10))
        assertFalse(AppLock.shouldRelock(enabled = true, backgroundedAt = 1_000, now = 1_000 + AppLock.GRACE_MS))
        assertTrue(AppLock.shouldRelock(enabled = true, backgroundedAt = 1_000, now = 1_001 + AppLock.GRACE_MS))
    }
    @Test fun neverBackgroundedMeansNoRelock() {
        assertFalse(AppLock.shouldRelock(enabled = true, backgroundedAt = 0, now = 10_000_000))
    }
    @Test fun phonePinIsAlwaysAllowedAsTheFallback() {
        val credential = androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL
        assertEquals(credential, AppLock.authenticators(29) and credential)
        assertEquals(credential, AppLock.authenticators(34) and credential)
    }
}
