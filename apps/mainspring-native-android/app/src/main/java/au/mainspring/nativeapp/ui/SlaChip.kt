package au.mainspring.nativeapp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.SlaKind

/** Late / At risk / Unscheduled aging chip. Late is the error tone; the others are the primary tone. */
@Composable fun SlaChip(kind: SlaKind, modifier: Modifier = Modifier) {
    val tone = if(kind == SlaKind.LATE) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
    val described = modifier.semantics { contentDescription = "SLA: ${kind.label}" }
    if(LocalCalibre.current) {
        Row(described, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Box(Modifier.size(6.dp).background(tone, androidx.compose.foundation.shape.CircleShape))
            Text(kind.label, style = MaterialTheme.typography.labelMedium, color = tone)
        }
        return
    }
    Surface(described, shape = MaterialTheme.shapes.small, color = tone.copy(alpha = 0.12f)) {
        Text(kind.label, Modifier.padding(horizontal = 8.dp, vertical = 3.dp), style = MaterialTheme.typography.labelMedium, color = tone)
    }
}
