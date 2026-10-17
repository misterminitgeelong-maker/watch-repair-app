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
 * Small line icon for a More tool route or group key (24 unit grid, round caps). Purely decorative:
 * the label next to it carries the meaning, so it is hidden from TalkBack.
 */
@Composable fun ToolIcon(key: String, modifier: Modifier = Modifier, size: Dp = 22.dp, color: Color = MaterialTheme.colorScheme.primary) {
    Canvas(modifier.size(size).clearAndSetSemantics { }) {
        val s = this.size.width / 24f
        val w = 1.6f * s
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
        when(key) {
            "workshop", "repairQueue", "auto_jobs", "jobs" -> { rect(5f, 4f, 14f, 17f); ln(9f, 9f, 15f, 9f); ln(9f, 13f, 15f, 13f); ln(9f, 17f, 12f, 17f) }
            "customerOrders", "stock", "toolsWorkshop" -> { poly(12f, 3f, 20f, 7.5f, 20f, 16.5f, 12f, 21f, 4f, 16.5f, 4f, 7.5f, close = true); ln(4f, 7.5f, 12f, 12f); ln(20f, 7.5f, 12f, 12f); ln(12f, 12f, 12f, 21f) }
            "catalogue" -> { poly(4f, 5f, 12f, 7f, 12f, 20f, 4f, 18f, close = true); poly(20f, 5f, 12f, 7f, 12f, 20f, 20f, 18f, close = true) }
            "shoeServices", "shoe_jobs" -> { poly(4f, 7f, 9f, 7f, 10f, 12f, 20f, 15f, 20f, 18f, 4f, 18f, close = true); ln(4f, 15f, 20f, 15f) }
            "bookingRequests" -> { rect(4f, 5f, 16f, 15f); ln(4f, 10f, 20f, 10f); ln(8f, 3f, 8f, 7f); ln(16f, 3f, 16f, 7f) }
            "mobile", "dispatch", "toolsMobile" -> { rect(2.5f, 7f, 12f, 9f, 1.5f); poly(14.5f, 10f, 19f, 10f, 21.5f, 13f, 21.5f, 16f, 14.5f, 16f); circle(7f, 17.5f, 2f); circle(17.5f, 17.5f, 2f) }
            "route" -> { poly(12f, 21f, 6f, 11f, 6.5f, 7f, 9.5f, 4f, 14.5f, 4f, 17.5f, 7f, 18f, 11f, close = true); circle(12f, 9.5f, 2.4f) }
            "dispatchPool" -> { poly(12f, 4f, 21f, 9f, 12f, 14f, 3f, 9f, close = true); poly(3f, 13f, 12f, 18f, 21f, 13f); poly(3f, 16.5f, 12f, 21.5f, 21f, 16.5f) }
            "counterSale" -> { rect(3f, 8f, 18f, 12f); poly(5f, 8f, 7f, 4f, 17f, 4f, 19f, 8f); circle(12f, 14f, 2.4f) }
            "sendBookingRequest" -> { poly(21f, 3f, 3f, 10.5f, 10f, 13.5f, 13f, 21f, close = true); ln(10f, 13.5f, 21f, 3f) }
            "leads", "inbox" -> { poly(3f, 13f, 6f, 5f, 18f, 5f, 21f, 13f, 21f, 19f, 3f, 19f, close = true); poly(3f, 13f, 8f, 13f, 9.5f, 15.5f, 14.5f, 15.5f, 16f, 13f, 21f, 13f) }
            "prospects" -> { circle(12f, 12f, 8f); circle(12f, 12f, 4f) }
            "toolkit" -> { rect(3f, 8f, 18f, 12f); poly(9f, 8f, 9f, 5f, 15f, 5f, 15f, 8f); ln(3f, 13f, 21f, 13f) }
            "money" -> { circle(12f, 12f, 8.5f); poly(14.5f, 9f, 11f, 9f, 9.5f, 10.5f, 11f, 12f, 13f, 12f, 14.5f, 13.5f, 13f, 15f, 9.5f, 15f); ln(12f, 7f, 12f, 9f); ln(12f, 15f, 12f, 17f) }
            "quotes" -> { poly(6f, 3f, 14f, 3f, 19f, 8f, 19f, 21f, 6f, 21f, close = true); poly(14f, 3f, 14f, 8f, 19f, 8f); ln(9f, 13f, 16f, 13f); ln(9f, 17f, 14f, 17f) }
            "invoices" -> { poly(5f, 3f, 19f, 3f, 19f, 21f, 16f, 19f, 12f, 21f, 8f, 19f, 5f, 21f, close = true); ln(9f, 8f, 15f, 8f); ln(9f, 12f, 15f, 12f) }
            "revenueControl" -> { drawArc(color, 180f, 180f, false, p(3f, 6f), Size(18f * s, 18f * s), style = st); ln(12f, 15f, 16f, 9.5f); ln(3f, 15f, 5f, 15f); ln(19f, 15f, 21f, 15f) }
            "reports", "reportExtras", "financeReport" -> { ln(4f, 3f, 4f, 20f); ln(4f, 20f, 21f, 20f); ln(9f, 16f, 9f, 11f); ln(14f, 16f, 14f, 7f); ln(19f, 16f, 19f, 12f) }
            "database" -> { drawOval(color, p(5f, 3.5f), Size(14f * s, 5f * s), style = st); ln(5f, 6f, 5f, 18f); ln(19f, 6f, 19f, 18f); drawArc(color, 0f, 180f, false, p(5f, 11.5f), Size(14f * s, 5f * s), style = st); drawArc(color, 0f, 180f, false, p(5f, 15.5f), Size(14f * s, 5f * s), style = st) }
            "people", "customers" -> { circle(9f, 8f, 3.4f); drawArc(color, 200f, 140f, false, p(3f, 14f), Size(12f * s, 12f * s), style = st); circle(17f, 9f, 2.8f); drawArc(color, 200f, 140f, false, p(12.5f, 14.5f), Size(9f * s, 9f * s), style = st) }
            "businessAccounts" -> { rect(5f, 3f, 14f, 18f, 1.5f); ln(9f, 8f, 10f, 8f); ln(14f, 8f, 15f, 8f); ln(9f, 12f, 10f, 12f); ln(14f, 12f, 15f, 12f); ln(10.5f, 21f, 10.5f, 17f); ln(13.5f, 21f, 13.5f, 17f) }
            "team", "toolsShop" -> { circle(12f, 8f, 3.6f); drawArc(color, 195f, 150f, false, p(5f, 13f), Size(14f * s, 14f * s), style = st) }
            "shop", "shopSettings" -> { poly(3f, 9f, 5f, 4f, 19f, 4f, 21f, 9f); poly(3f, 9f, 3f, 11f, 21f, 11f, 21f, 9f); poly(5f, 11f, 5f, 20f, 19f, 20f, 19f, 11f); rect(10f, 14f, 4f, 6f, 0.5f) }
            "queuedChanges" -> { drawArc(color, 200f, 250f, false, p(4f, 4f), Size(16f * s, 16f * s), style = st); poly(4f, 3f, 4f, 8f, 9f, 8f); ln(12f, 8f, 12f, 12f); ln(12f, 12f, 15f, 14f) }
            "accounts" -> { circle(12f, 12f, 9f); circle(12f, 10f, 3f); drawArc(color, 205f, 130f, false, p(7f, 13f), Size(10f * s, 10f * s), style = st) }
            "settings" -> { ln(4f, 7f, 20f, 7f); ln(4f, 12f, 20f, 12f); ln(4f, 17f, 20f, 17f); circle(9f, 7f, 2f); circle(15f, 12f, 2f); circle(8f, 17f, 2f) }
            "check" -> { circle(12f, 12f, 9f); poly(8f, 12.5f, 11f, 15.5f, 16.5f, 9f) }
            "search" -> { circle(10.5f, 10.5f, 6f); ln(15f, 15f, 20f, 20f) }
            else -> { circle(12f, 12f, 8f); ln(12f, 8f, 12f, 12f); ln(12f, 12f, 15f, 14f) }
        }
    }
}
