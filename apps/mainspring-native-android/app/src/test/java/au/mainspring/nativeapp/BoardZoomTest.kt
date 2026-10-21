package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.screens.BoardZoom
import au.mainspring.nativeapp.ui.screens.BoardZoomMemory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class BoardZoomTest {
    @Test fun aBoardThatAlreadyFitsNeverZoomsOutBelowNormal() {
        assertEquals(1f, BoardZoom.fitScale(viewportDp = 400f, contentDp = 300f), 0.0001f)
    }

    @Test fun fitScaleMakesEveryColumnFitTheScreen() {
        val content = BoardZoom.contentWidth(columnCount = 7, columnWidthDp = 168f)
        val fit = BoardZoom.fitScale(viewportDp = 390f, contentDp = content)
        assertTrue(fit < 1f)
        assertEquals(390f, content * fit, 0.5f)
    }

    @Test fun veryWideBoardsStopAtTheAbsoluteMinimum() {
        assertEquals(BoardZoom.ABSOLUTE_MIN, BoardZoom.fitScale(viewportDp = 390f, contentDp = 10_000f), 0.0001f)
    }

    @Test fun pinchIsKeptBetweenFitAndTwoTimes() {
        val fit = 0.4f
        assertEquals(2f, BoardZoom.apply(1.8f, 1.5f, fit), 0.0001f)
        assertEquals(0.4f, BoardZoom.apply(0.5f, 0.5f, fit), 0.0001f)
        assertEquals(1.2f, BoardZoom.apply(1f, 1.2f, fit), 0.0001f)
    }

    @Test fun savedZoomIsClampedWhenTheScreenGetsNarrower() {
        assertEquals(0.5f, BoardZoom.clampTo(0.3f, fit = 0.5f), 0.0001f)
        assertEquals(2f, BoardZoom.clampTo(3f, fit = 0.5f), 0.0001f)
    }

    @Test fun zoomIsRememberedPerBoardAndNormalSizeForgetsIt() {
        BoardZoomMemory.clear()
        BoardZoomMemory.set("watch", 0.6f); BoardZoomMemory.set("shoe", 1.5f)
        assertEquals(0.6f, BoardZoomMemory.get("watch")!!, 0.0001f); assertEquals(1.5f, BoardZoomMemory.get("shoe")!!, 0.0001f)
        BoardZoomMemory.set("watch", 1f)
        assertNull(BoardZoomMemory.get("watch")); assertEquals(1.5f, BoardZoomMemory.get("shoe")!!, 0.0001f)
        BoardZoomMemory.clear()
    }
}
