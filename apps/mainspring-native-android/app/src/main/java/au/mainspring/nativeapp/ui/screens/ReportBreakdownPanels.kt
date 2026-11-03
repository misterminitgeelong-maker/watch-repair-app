package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.ReportCharts
import au.mainspring.nativeapp.api.GstCategory
import au.mainspring.nativeapp.api.GstSummaryResponse
import au.mainspring.nativeapp.api.TechBreakdownRow
import au.mainspring.nativeapp.api.TrendMonth
import au.mainspring.nativeapp.ui.DetailRow
import au.mainspring.nativeapp.ui.FlatPanel
import au.mainspring.nativeapp.ui.LocalCalibre
import au.mainspring.nativeapp.ui.MonoLabel
import au.mainspring.nativeapp.ui.formatCents

private fun cents(value: Long) = formatCents(value.coerceIn(Int.MIN_VALUE.toLong(), Int.MAX_VALUE.toLong()).toInt(), "AUD")

/** GST collected on paid watch and mobile invoices for the selected window (shoe repairs carry no GST fields on the server). */
@Composable internal fun GstBreakdownPanel(gst: GstSummaryResponse) {
    FlatPanel(Modifier.testTag("gst-breakdown")) {
        Text("GST collected", style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
        listOf("Watch repairs" to gst.watch, "Mobile services" to gst.mobile, "Combined" to gst.combined).forEach { (label, bucket) ->
            if(bucket != null) GstRow(label, bucket)
        }
        Text("Shoe repairs are not included: they have no GST tracking.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable private fun GstRow(label: String, bucket: GstCategory) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        if(LocalCalibre.current) MonoLabel(label.uppercase()) else Text(label, style = MaterialTheme.typography.labelLarge)
        DetailRow("GST", cents(bucket.gstCents))
        DetailRow("Subtotal (ex GST)", cents(bucket.subtotalCents))
        DetailRow("Total", cents(bucket.totalCents) + " (" + bucket.invoiceCount + " paid)")
    }
}

/** Ranked horizontal bars of logged work minutes per technician. */
@Composable internal fun TechLeaderboardPanel(rows: List<TechBreakdownRow>) {
    FlatPanel(Modifier.testTag("tech-leaderboard")) {
        Text("Technician leaderboard", style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
        Text("Logged work time, all time.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        val fractions = ReportCharts.fractions(rows.map { it.totalMinutes.toLong() })
        rows.forEachIndexed { index, row ->
            val summary = "${index + 1}. ${row.userName}, ${ReportCharts.minutesLabel(row.totalMinutes)} on ${row.jobsCount} jobs"
            Column(Modifier.fillMaxWidth().semantics(mergeDescendants = true) { contentDescription = summary }, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("${index + 1}. ${row.userName}", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
                    Text(ReportCharts.minutesLabel(row.totalMinutes) + " · " + row.jobsCount + " jobs", style = MaterialTheme.typography.labelLarge)
                }
                Bar(fractions[index], Modifier.fillMaxWidth().height(8.dp), if(index == 0) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface)
            }
        }
    }
}

@Composable private fun Bar(fraction: Float, modifier: Modifier, color: androidx.compose.ui.graphics.Color) {
    Box(modifier.background(MaterialTheme.colorScheme.surfaceVariant)) {
        Box(Modifier.fillMaxWidth(fraction.coerceIn(0f, 1f)).fillMaxHeight().background(color))
    }
}

/** Monthly revenue and jobs-opened as two compact column charts drawn from plain boxes (no chart library). */
@Composable internal fun TrendsPanel(months: List<TrendMonth>) {
    FlatPanel(Modifier.testTag("trend-charts")) {
        Text("Monthly trends", style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
        if(months.isEmpty()) { Text("No trend data yet.", style = MaterialTheme.typography.bodyMedium); return@FlatPanel }
        TrendColumns("Revenue", months.map { it.month }, months.map { it.revenueCents }, { ReportCharts.compactMoney(it) }, MaterialTheme.colorScheme.primary)
        TrendColumns("Jobs opened", months.map { it.month }, months.map { it.jobsOpened.toLong() }, { it.toString() }, MaterialTheme.colorScheme.onSurface)
    }
}

@Composable private fun TrendColumns(title: String, labels: List<String>, values: List<Long>, format: (Long) -> String, color: androidx.compose.ui.graphics.Color) {
    val fractions = ReportCharts.fractions(values)
    val description = title + ": " + labels.indices.joinToString(", ") { ReportCharts.monthLabel(labels[it]) + " " + format(values[it]) }
    Column(Modifier.fillMaxWidth().semantics(mergeDescendants = true) { contentDescription = description }, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if(LocalCalibre.current) MonoLabel(title.uppercase()) else Text(title, style = MaterialTheme.typography.labelLarge)
        Row(Modifier.fillMaxWidth().clearAndSetSemantics { }, horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Bottom) {
            labels.indices.forEach { i ->
                Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(format(values[i]), style = MaterialTheme.typography.labelSmall, maxLines = 1)
                    Spacer(Modifier.height(2.dp))
                    Box(Modifier.fillMaxWidth().height((4 + fractions[i] * 76).dp).background(color))
                    Text(ReportCharts.monthLabel(labels[i]), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}
