package au.mainspring.nativeapp.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Small UI glyphs for the web-style service screens (lucide-like line icons on a 24 unit grid): plus, chevrons, shield,
 * camera, upload, phone, warning, pin, calendar, list, check, dots, shoe. Decorative: the label beside it carries the meaning.
 */
@Composable fun GlyphIcon(name: String, modifier: Modifier = Modifier, size: Dp = 18.dp, color: Color = MaterialTheme.colorScheme.onSurfaceVariant) {
    Canvas(modifier.size(size).clearAndSetSemantics { }) {
        val s = this.size.width / 24f
        val w = 1.8f * s
        val st = Stroke(w, cap = StrokeCap.Round, join = StrokeJoin.Round)
        fun p(x: Float, y: Float) = Offset(x * s, y * s)
        fun ln(x1: Float, y1: Float, x2: Float, y2: Float) = drawLine(color, p(x1, y1), p(x2, y2), w, cap = StrokeCap.Round)
        fun rect(x: Float, y: Float, wd: Float, h: Float, r: Float = 2f) = drawRoundRect(color, p(x, y), Size(wd * s, h * s), CornerRadius(r * s), style = st)
        fun circle(cx: Float, cy: Float, r: Float) = drawCircle(color, r * s, p(cx, cy), style = st)
        fun poly(vararg pts: Float, close: Boolean = false) {
            val path = Path(); path.moveTo(pts[0] * s, pts[1] * s)
            for(i in 2 until pts.size step 2) path.lineTo(pts[i] * s, pts[i + 1] * s)
            if(close) path.close()
            drawPath(path, color, style = st)
        }
        when(name) {
            "plus" -> { ln(12f, 5f, 12f, 19f); ln(5f, 12f, 19f, 12f) }
            "chevronDown" -> poly(6f, 9f, 12f, 15f, 18f, 9f)
            "chevronUp" -> poly(6f, 15f, 12f, 9f, 18f, 15f)
            "chevronLeft" -> poly(15f, 5f, 8f, 12f, 15f, 19f)
            "chevronRight" -> poly(9f, 5f, 16f, 12f, 9f, 19f)
            "shield" -> poly(12f, 3f, 19f, 6f, 19f, 12f, 12f, 21f, 5f, 12f, 5f, 6f, close = true)
            "camera" -> { rect(3f, 7f, 18f, 13f, 2.5f); poly(8f, 7f, 9.5f, 4f, 14.5f, 4f, 16f, 7f); circle(12f, 13.5f, 3.2f) }
            "upload" -> { ln(12f, 16f, 12f, 5f); poly(7f, 9.5f, 12f, 4.5f, 17f, 9.5f); ln(5f, 19.5f, 19f, 19.5f) }
            "phone" -> { rect(6.5f, 2.5f, 11f, 19f, 2.5f); ln(10.5f, 18.5f, 13.5f, 18.5f) }
            "warning" -> { poly(12f, 4f, 21.5f, 20f, 2.5f, 20f, close = true); ln(12f, 10f, 12f, 14f); ln(12f, 17f, 12f, 17.1f) }
            "pin" -> { poly(12f, 21f, 6f, 11f, 6.5f, 7f, 9.5f, 4f, 14.5f, 4f, 17.5f, 7f, 18f, 11f, close = true); circle(12f, 9.5f, 2.4f) }
            "calendar" -> { rect(4f, 5f, 16f, 15f, 2f); ln(4f, 10f, 20f, 10f); ln(8f, 3f, 8f, 7f); ln(16f, 3f, 16f, 7f) }
            "list" -> { ln(10f, 7f, 20f, 7f); ln(10f, 12f, 20f, 12f); ln(10f, 17f, 20f, 17f); ln(4f, 7f, 5f, 7f); ln(4f, 12f, 5f, 12f); ln(4f, 17f, 5f, 17f) }
            "check" -> poly(5f, 12.5f, 10f, 17.5f, 19f, 7f)
            "dots" -> { listOf(5f, 12f, 19f).forEach { x -> drawCircle(color, 1.7f * s, p(x, 12f)) } }
            "shoe" -> { poly(4f, 7f, 9f, 7f, 10f, 12f, 20f, 15f, 20f, 18f, 4f, 18f, close = true); ln(4f, 15f, 20f, 15f) }
            "search" -> { circle(10.5f, 10.5f, 6f); ln(15f, 15f, 20f, 20f) }
            "close" -> { ln(6f, 6f, 18f, 18f); ln(18f, 6f, 6f, 18f) }
            else -> circle(12f, 12f, 8f)
        }
    }
}
