package au.mainspring.nativeapp

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.pinch
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.BoardZoomMemory
import au.mainspring.nativeapp.ui.screens.ZoomableBoard
import org.junit.Assert
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/** Pinching scales the whole board; one-finger tap and sideways scrolling keep working; the reset pill and double-tap go back to normal. */
class ZoomableBoardTest {
    @get:Rule val compose = createComposeRule()
    private var opened = 0

    @Before fun setup() { BoardZoomMemory.clear(); opened = 0 }
    @org.junit.After fun cleanup() { BoardZoomMemory.clear() }

    private fun board() = compose.setContent { MainspringTheme {
        ZoomableBoard("test", columnCount = 6, columnWidth = 168.dp) {
            Row(Modifier.horizontalScroll(rememberScrollState()).testTag("board-row").padding(12.dp)) {
                repeat(6) { n -> Box(Modifier.size(168.dp).padding(4.dp).testTag("card-$n").clickable { opened++ }) { Text("Job $n") } }
            }
        }
    } }

    @Test fun pinchingOutShowsTheResetPillAndTapStillOpens() {
        board()
        compose.onNodeWithTag("zoom-reset").assertDoesNotExist()
        compose.onNodeWithTag("zoom-board-test").performTouchInput {
            pinch(Offset(center.x - 60f, center.y), Offset(center.x - 200f, center.y), Offset(center.x + 60f, center.y), Offset(center.x + 200f, center.y))
        }
        compose.onNodeWithTag("zoom-reset").assertExists()
        compose.onNodeWithTag("card-0").performClick()
        Assert.assertEquals(1, opened)
    }

    @Test fun resetPillReturnsToNormalSize() {
        board()
        compose.onNodeWithTag("zoom-board-test").performTouchInput {
            pinch(Offset(center.x - 60f, center.y), Offset(center.x - 200f, center.y), Offset(center.x + 60f, center.y), Offset(center.x + 200f, center.y))
        }
        compose.onNodeWithTag("zoom-reset").performClick()
        compose.onNodeWithTag("zoom-reset").assertDoesNotExist()
    }

    @Test fun zoomIsKeptPerBoardInMemory() {
        BoardZoomMemory.set("test", 1.5f)
        board()
        compose.onNodeWithTag("zoom-reset").assertExists()
    }

    private fun pillPercent(): Int {
        val text = compose.onNodeWithTag("zoom-reset").fetchSemanticsNode().config[androidx.compose.ui.semantics.SemanticsProperties.Text].joinToString("") { it.text }
        return Regex("(\\d+)%").find(text)!!.groupValues[1].toInt()
    }

    /** Realistic two-finger spread and pinch with many small moves and a real finger lift, like a thumb and finger on a phone. */
    private fun pinchBy(startGap: Float, endGap: Float) = compose.onNodeWithTag("zoom-board-test").performTouchInput {
        pinch(Offset(center.x - startGap / 2, center.y), Offset(center.x - endGap / 2, center.y), Offset(center.x + startGap / 2, center.y), Offset(center.x + endGap / 2, center.y), durationMillis = 600)
    }

    @Test fun pinchingOutKeepsZoomingDownToFitEveryColumnAndStaysThere() {
        board()
        pinchBy(startGap = 400f, endGap = 40f)
        compose.waitForIdle()
        val fitPercent = pillPercent()
        Assert.assertTrue("zoomed out well below 100%, was $fitPercent%", fitPercent in 20..70)
        compose.waitForIdle(); Thread.sleep(500)
        Assert.assertEquals("scale must stay after the fingers lift", fitPercent, pillPercent())
        pinchBy(startGap = 400f, endGap = 40f)   // pinching further does not go past the fit size
        compose.waitForIdle()
        Assert.assertEquals(fitPercent, pillPercent())
    }

    @Test fun pinchingInGrowsToAboutTwoTimesAndStays() {
        board()
        pinchBy(startGap = 60f, endGap = 500f)
        compose.waitForIdle()
        val zoomed = pillPercent()
        Assert.assertTrue("zoomed in to between 150% and 200%, was $zoomed%", zoomed in 150..200)
        Thread.sleep(500)
        Assert.assertEquals(zoomed, pillPercent())
    }

    @Test fun successivePinchesAccumulateInsteadOfRestartingFromNormal() {
        board()
        pinchBy(startGap = 100f, endGap = 150f)
        compose.waitForIdle()
        val first = pillPercent()
        pinchBy(startGap = 100f, endGap = 150f)
        compose.waitForIdle()
        Assert.assertTrue("second pinch continues from the first ($first% then ${pillPercent()}%)", pillPercent() > first)
    }
}
