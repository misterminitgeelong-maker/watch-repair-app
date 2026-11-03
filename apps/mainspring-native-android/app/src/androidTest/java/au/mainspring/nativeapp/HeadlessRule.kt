package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import org.junit.rules.TestRule
import org.junit.runner.Description
import org.junit.runners.model.Statement

/**
 * Stand-in for `createComposeRule()` in tests that only drive view models and never render UI.
 *
 * `createComposeRule()` launches an empty ComponentActivity through ActivityScenario and, at teardown, waits for it to reach
 * DESTROYED. On a loaded emulator that wait intermittently times out ("Activity never becomes requested state [DESTROYED]
 * (last lifecycle transition = PAUSED)"), failing tests whose bodies passed. These tests never touch the activity, so this rule
 * launches none: it only supplies the `waitUntil` / `waitForIdle` polling the tests used. View models still run their
 * coroutines on the real main looper (Dispatchers.Main.immediate), which exists without any activity.
 */
class HeadlessRule : TestRule {
    override fun apply(base: Statement, description: Description): Statement = base

    /** Polls [condition] on the calling (instrumentation) thread, like ComposeTestRule.waitUntil. */
    fun waitUntil(timeoutMillis: Long = 1_000, condition: () -> Boolean) {
        val deadline = System.nanoTime() + timeoutMillis * 1_000_000
        while (!condition()) {
            if (System.nanoTime() > deadline) throw AssertionError("Condition still not satisfied after $timeoutMillis ms")
            Thread.sleep(10)
        }
    }

    /** Lets work already posted to the main looper run. */
    fun waitForIdle() = InstrumentationRegistry.getInstrumentation().waitForIdleSync()
}
