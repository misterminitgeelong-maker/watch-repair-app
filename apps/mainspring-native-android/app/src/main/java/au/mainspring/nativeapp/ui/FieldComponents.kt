package au.mainspring.nativeapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(text.uppercase(), modifier = modifier.padding(vertical = 8.dp), style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable fun FlatPanel(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Surface(modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), shape = MaterialTheme.shapes.small) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
    }
}

@Composable fun DetailRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(label, Modifier.weight(0.4f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value.ifBlank { "Not recorded" }, Modifier.weight(0.6f), style = MaterialTheme.typography.bodySmall,
            textAlign = androidx.compose.ui.text.style.TextAlign.End)
    }
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable fun StatusPill(status: String) {
    val dark = MaterialTheme.colorScheme.background.red < 0.2f
    val (background, foreground) = when(status) {
        "booked", "booking_confirmed", "booking_scheduled" -> if(dark) Color(0xFF172B3B) to Color(0xFF9ACAF2) else Color(0xFFE7F0FF) to Color(0xFF315F96)
        "work_completed", "invoice_paid", "paid" -> if(dark) Color(0xFF1A3427) to Color(0xFFA2DBB6) else Color(0xFFE6F3E9) to Color(0xFF326747)
        "awaiting_go_ahead", "quote_sent", "awaiting_confirmation" -> if(dark) Color(0xFF3C3019) to Color(0xFFEED59B) else Color(0xFFFFF3DA) to Color(0xFF866020)
        else -> MaterialTheme.colorScheme.secondaryContainer to MaterialTheme.colorScheme.onSecondaryContainer
    }
    Surface(color = background, contentColor = foreground, shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp)) {
        Text(status.replace('_', ' ').replaceFirstChar { it.uppercase() }, Modifier.padding(horizontal = 8.dp, vertical = 3.dp), style = MaterialTheme.typography.labelSmall)
    }
}

@Composable fun MetricStrip(values: List<Pair<String, String>>, modifier: Modifier = Modifier) {
    Surface(modifier.fillMaxWidth(),color=MaterialTheme.colorScheme.surface,shape=androidx.compose.foundation.shape.RoundedCornerShape(10.dp)) {
        Row(Modifier.height(IntrinsicSize.Min)) {
            values.forEachIndexed {index,(label,value) ->
                Column(Modifier.weight(1f).padding(12.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                    Text(label.uppercase(),style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(value,style=MaterialTheme.typography.titleLarge,fontWeight=FontWeight.SemiBold)
                }
                if(index<values.lastIndex) VerticalDivider(Modifier.fillMaxHeight().padding(vertical=12.dp),color=MaterialTheme.colorScheme.outlineVariant)
            }
        }
    }
}

/** Small scalable outline icons, kept local so every navigation item has a real glyph. */
@Composable fun FieldIcon(name: String, color: Color = MaterialTheme.colorScheme.onSurfaceVariant) {
    Canvas(Modifier.size(22.dp)) {
        val scale = size.width / 24f
        fun point(x: Float,y: Float) = Offset(x*scale,y*scale)
        fun line(x: Float,y: Float,x2: Float,y2: Float) = drawLine(color,point(x,y),point(x2,y2),1.5f*scale)
        when(name) {
            "Jobs" -> { drawCircle(color,5f*scale,point(8f,8f),style = Stroke(1.5f*scale)); line(11f,12f,21f,22f); line(17f,18f,20f,15f); line(19f,20f,22f,17f) }
            "Map" -> { val p=Path(); p.moveTo(2f*scale,5f*scale); p.lineTo(8f*scale,2f*scale); p.lineTo(16f*scale,5f*scale); p.lineTo(22f*scale,2f*scale); p.lineTo(22f*scale,19f*scale); p.lineTo(16f*scale,22f*scale); p.lineTo(8f*scale,19f*scale); p.lineTo(2f*scale,22f*scale); p.close(); drawPath(p,color,style=Stroke(1.5f*scale)); line(8f,2f,8f,19f); line(16f,5f,16f,22f) }
            "Pool" -> { for(y in listOf(5f,10f,15f)) { line(3f,y,12f,y-3f); line(12f,y-3f,21f,y); line(3f,y,12f,y+4f); line(12f,y+4f,21f,y) } }
            "POS" -> { drawRect(color,point(2f,5f),Size(20f*scale,14f*scale),style=Stroke(1.5f*scale)); line(2f,9f,22f,9f) }
            "Home" -> { line(2f,11f,12f,2f); line(12f,2f,22f,11f); line(5f,9f,5f,22f); line(5f,22f,19f,22f); line(19f,22f,19f,9f); line(10f,22f,10f,15f); line(10f,15f,14f,15f); line(14f,15f,14f,22f) }
            "Reports" -> { line(3f,2f,3f,22f); line(3f,22f,22f,22f); line(8f,18f,8f,12f); line(13f,18f,13f,6f); line(18f,18f,18f,9f) }
            "Stock" -> { drawRect(color,point(4f,4f),Size(16f*scale,18f*scale),style=Stroke(1.5f*scale)); line(8f,2f,16f,2f); for(y in listOf(9f,13f,17f)) line(8f,y,16f,y) }
            else -> { for(y in listOf(6f,12f,18f)) line(4f,y,20f,y) }
        }
    }
}
