package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.layout
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlin.math.roundToInt

/** Pure rules for board zoom, so they can be unit tested. */
object BoardZoom {
    const val MAX_SCALE = 2f
    /** Never zoom out past a quarter size, even for a board with very many columns. */
    const val ABSOLUTE_MIN = 0.25f
    private val gap = 8f
    private val sidePadding = 24f

    /** Width of a whole board in dp: every column plus gaps and the page padding. */
    fun contentWidth(columnCount: Int, columnWidthDp: Float): Float = columnCount.coerceAtLeast(1) * (columnWidthDp + gap) + sidePadding

    /** The scale at which every column fits on screen at once (1 when the board already fits). */
    fun fitScale(viewportDp: Float, contentDp: Float): Float =
        if(contentDp <= 0f || viewportDp <= 0f) 1f else (viewportDp / contentDp).coerceIn(ABSOLUTE_MIN, 1f)

    /** New scale after a pinch of [factor], kept between the fit-everything size and 2x. */
    fun apply(current: Float, factor: Float, fit: Float): Float = (current * factor).coerceIn(fit.coerceAtMost(1f), MAX_SCALE)

    fun clampTo(scale: Float, fit: Float): Float = scale.coerceIn(fit.coerceAtMost(1f), MAX_SCALE)
}

/** Zoom level per board, remembered for the life of the app process only. */
object BoardZoomMemory {
    private val levels = HashMap<String, Float>()
    fun get(board: String): Float? = levels[board]
    fun set(board: String, scale: Float) { if(scale == 1f) levels.remove(board) else levels[board] = scale }
    fun clear() = levels.clear()
}

/**
 * Two-finger pinch scales the whole board: zoom out until every column fits on screen, zoom in up to 2x for bigger touch targets.
 * One-finger gestures are never touched, so tap to open, press and hold menus and sideways column scrolling keep working at any zoom.
 * Double-tap on empty board space (or the reset pill) returns to normal size.
 */
@Composable fun ZoomableBoard(boardKey: String, columnCount: Int, columnWidth: Dp, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    val density = LocalDensity.current
    BoxWithConstraints(modifier.fillMaxWidth().testTag("zoom-board-$boardKey")) {
        val fontFactor = 1f + (density.fontScale - 1f).coerceAtLeast(0f) * 0.6f
        val fit = BoardZoom.fitScale(maxWidth.value, BoardZoom.contentWidth(columnCount, columnWidth.value * fontFactor))
        var stored by remember(boardKey) { mutableFloatStateOf(BoardZoomMemory.get(boardKey) ?: 1f) }
        val scale = BoardZoom.clampTo(stored, fit)
        fun change(next: Float) { stored = next; BoardZoomMemory.set(boardKey, next) }
        // The gesture block below lives across recompositions, so it must read the CURRENT scale and fit, not the values from when it started:
        // a captured scale would restart every pinch event from 100% and the board could never zoom past a couple of percent.
        val liveFit by rememberUpdatedState(fit)
        val liveChange by rememberUpdatedState(::change)
        Box(Modifier
            .pointerInput(Unit) {
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial)
                    do {
                        val event = awaitPointerEvent(PointerEventPass.Initial)
                        if(event.changes.count { it.pressed } >= 2) {
                            val zoom = event.calculateZoom()
                            // Read the state itself: several touch events can arrive before the next recomposition.
                            if(zoom != 1f) { liveChange(BoardZoom.apply(BoardZoom.clampTo(stored, liveFit), zoom, liveFit)); event.changes.forEach { if(it.pressed) it.consume() } }
                        }
                    } while(event.changes.any { it.pressed })
                }
            }
            .pointerInput(Unit) { detectTapGestures(onDoubleTap = { change(1f) }) }
        ) {
            Box(Modifier.zoomLayout(scale)) { content() }
            if(scale != 1f) Surface({ change(1f) }, Modifier.align(Alignment.TopEnd).padding(top = 4.dp, end = 8.dp).heightIn(min = 40.dp).testTag("zoom-reset")
                .semantics { contentDescription = "Reset board zoom" }, shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.surface,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), shadowElevation = 2.dp) {
                Box(Modifier.padding(horizontal = 12.dp), contentAlignment = Alignment.Center) {
                    Text("${(scale * 100).roundToInt()}% · Reset", style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

/** Lays the board out at 1/scale of the available width and then draws it scaled, so layout, touch and drawing all agree. */
private fun Modifier.zoomLayout(scale: Float): Modifier = layout { measurable, constraints ->
    val inner = if(constraints.hasBoundedWidth && scale != 1f) constraints.copy(maxWidth = (constraints.maxWidth / scale).roundToInt()) else constraints
    val placeable = measurable.measure(inner)
    layout((placeable.width * scale).roundToInt(), (placeable.height * scale).roundToInt()) {
        placeable.placeWithLayer(0, 0) { scaleX = scale; scaleY = scale; transformOrigin = TransformOrigin(0f, 0f) }
    }
}
