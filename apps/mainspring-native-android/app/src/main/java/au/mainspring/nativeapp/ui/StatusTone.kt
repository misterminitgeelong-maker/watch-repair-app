package au.mainspring.nativeapp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/** Meaning of a job or document status, independent of its exact wording. */
enum class StatusTone { Waiting, Ready, Progress, Late, Neutral }

private val LATE = setOf("no_go", "failed_job", "job_delayed", "declined", "overdue", "urgent", "cancelled", "canceled", "failed", "rejected", "expired", "void", "lost", "refused", "late")
private val READY = setOf("ready", "awaiting_collection", "work_completed", "completed", "complete", "collected", "paid", "invoice_paid", "delivered", "done", "accepted", "signed", "won", "active", "approved", "converted")
private val PROGRESS = setOf("in_progress", "working_on", "work_in_progress", "go_ahead", "en_route", "on_the_way", "started", "arrived", "in_repair", "working", "scheduled", "assigned", "contacted", "booked", "repairing")

/** Maps any status string (API snake_case or spaced display text) to a [StatusTone]. Unknown values are neutral. */
fun statusTone(status: String): StatusTone {
    val s = status.trim().lowercase().replace(Regex("[\\s\\-]+"), "_")
    return when {
        s.isEmpty() -> StatusTone.Neutral
        s in LATE -> StatusTone.Late
        s in READY -> StatusTone.Ready
        s.startsWith("awaiting") || s.startsWith("quote") || s.startsWith("waiting") || s.startsWith("pending") || s.startsWith("parts") || s == "on_hold" || s == "sent" || s == "partially_paid" || s == "part_paid" -> StatusTone.Waiting
        s in PROGRESS -> StatusTone.Progress
        s.contains("overdue") || s.contains("urgent") || s.contains("delayed") -> StatusTone.Late
        s.contains("progress") || s.contains("working") || s.contains("go_ahead") || s.contains("route") -> StatusTone.Progress
        s.startsWith("ready") || s.contains("complete") || s.contains("collected") || s.contains("paid") -> StatusTone.Ready
        else -> StatusTone.Neutral
    }
}

/** Tint, text and dot colours for a tone. Light text/tint pairs are at least 5.5:1, dark pairs at least 7:1. */
class ToneColors(val container: Color, val content: Color, val dot: Color)

@Composable fun toneColors(tone: StatusTone): ToneColors {
    val dark = isSystemInDarkTheme()
    LocalCalibrePalette.current.tones?.let { t ->
        return when(tone) { StatusTone.Waiting -> t.waiting; StatusTone.Ready -> t.ready; StatusTone.Progress -> t.progress; StatusTone.Late -> t.late; StatusTone.Neutral -> t.neutral }
    }
    return if(dark) when(tone) {
        StatusTone.Waiting -> ToneColors(Color(0xFF3A2D10), Color(0xFFF1CB7A), Color(0xFFE0A93A))
        StatusTone.Ready -> ToneColors(Color(0xFF1B3425), Color(0xFF9FD7B0), Color(0xFF5FB27C))
        StatusTone.Progress -> ToneColors(Color(0xFF17353A), Color(0xFF9ACFD4), Color(0xFF55AEB6))
        StatusTone.Late -> ToneColors(Color(0xFF3F1C1C), Color(0xFFF2A9A3), Color(0xFFE5675F))
        StatusTone.Neutral -> ToneColors(Color(0xFF2A2D2B), Color(0xFFC3C8C4), Color(0xFF8E948F))
    } else when(tone) {
        StatusTone.Waiting -> ToneColors(Color(0xFFFFF1D6), Color(0xFF7A4A00), Color(0xFFD9930D))
        StatusTone.Ready -> ToneColors(Color(0xFFDDEFE3), Color(0xFF1E5A33), Color(0xFF2E8B57))
        StatusTone.Progress -> ToneColors(Color(0xFFDCEBEC), Color(0xFF1F4D52), Color(0xFF2A7F88))
        StatusTone.Late -> ToneColors(Color(0xFFFBE1DE), Color(0xFF9B1C1C), Color(0xFFC62828))
        StatusTone.Neutral -> ToneColors(Color(0xFFEEEEEE), Color(0xFF4A4A4A), Color(0xFF8A8A8A))
    }
}

/** Soft tinted pill with a dot and the status words (never colour alone). */
@Composable fun TonePill(text: String, tone: StatusTone, modifier: Modifier = Modifier) {
    val c = toneColors(tone)
    Row(modifier.background(c.container, RoundedCornerShape(50)).padding(start = 8.dp, end = 10.dp, top = 3.dp, bottom = 3.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(Modifier.size(6.dp).background(c.dot, CircleShape))
        Text(text, style = MaterialTheme.typography.labelMedium, color = c.content, maxLines = 1)
    }
}

/** Pill for a row status line such as "Awaiting collection · Due today"; the tone comes from [status]. */
@Composable fun StatusLinePill(line: String, status: String, urgent: Boolean = false, modifier: Modifier = Modifier) =
    TonePill(line, if(urgent) StatusTone.Late else statusTone(status), modifier)
