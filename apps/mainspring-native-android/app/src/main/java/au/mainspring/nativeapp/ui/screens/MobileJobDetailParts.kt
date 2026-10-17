package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.AutoKeyJobRead
import au.mainspring.nativeapp.api.TeamUser
import au.mainspring.nativeapp.ui.GlyphIcon
import au.mainspring.nativeapp.ui.LocalCalibre
import au.mainspring.nativeapp.ui.TonePill
import au.mainspring.nativeapp.ui.calibreDisplayStyle
import au.mainspring.nativeapp.ui.formatShopDate
import au.mainspring.nativeapp.ui.statusLabel
import au.mainspring.nativeapp.ui.statusTone

internal fun issueSeverity(knowledge: com.google.gson.JsonObject?): String? =
    knowledge?.getAsJsonArray("known_issues")?.firstNotNullOfOrNull { e ->
        e.takeIf { it.isJsonObject }?.asJsonObject?.get("severity")?.takeIf { it.isJsonPrimitive }?.asString?.takeIf { it.isNotBlank() }
    }

/** Web phone header: "‹ Back to Mobile Services", serif "#AK-00001 · Title" with the accent underline, and an outlined "..." menu. */
@Composable internal fun MobileDetailHeader(job: AutoKeyJobRead?, onBack: () -> Unit, onRefresh: () -> Unit, onEdit: () -> Unit, refreshEnabled: Boolean, editEnabled: Boolean) {
    var menu by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background).statusBarsPadding().padding(start = 8.dp, end = 16.dp, top = 8.dp, bottom = 8.dp)) {
        TextButton(onBack, Modifier.heightIn(min = 48.dp).semantics { contentDescription = "Back" }, colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.onSurfaceVariant)) {
            GlyphIcon("chevronLeft", size = 18.dp, color = LocalContentColor.current)
            Spacer(Modifier.width(6.dp))
            Text("Back to Mobile Services", style = MaterialTheme.typography.bodyLarge)
        }
        Column(Modifier.padding(start = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(job?.let { (if (it.jobNumber.startsWith("#")) it.jobNumber else "#" + it.jobNumber) + " · " + it.title } ?: "Job", Modifier.padding(top = 4.dp),
                style = if (LocalCalibre.current) calibreDisplayStyle(MaterialTheme.typography.headlineMedium) else MaterialTheme.typography.headlineMedium, maxLines = 3)
            Box(Modifier.width(40.dp).height(3.dp).background(MaterialTheme.colorScheme.primary))
            Box(Modifier.padding(top = 4.dp)) {
                WebButton(null, { menu = true }, icon = "dots", tag = "detail-menu", description = "More actions")
                DropdownMenu(menu, { menu = false }) {
                    DropdownMenuItem(text = { Text("Refresh") }, enabled = refreshEnabled, onClick = { menu = false; onRefresh() })
                    DropdownMenuItem(text = { Text("Edit") }, enabled = editEnabled, onClick = { menu = false; onEdit() })
                }
            }
        }
    }
}

/** Pink "VEHICLE WARNING" card (web): warning icon, severity chip, issue count and a "Show" link. */
@Composable internal fun VehicleWarningCard(count: Int, severity: String?, onShow: () -> Unit) {
    val red = Color(0xFF9B1C1C)
    Surface(Modifier.fillMaxWidth().testTag("vehicle-warning"), shape = RoundedCornerShape(6.dp), color = MaterialTheme.colorScheme.primaryContainer,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.35f))) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                GlyphIcon("warning", size = 16.dp, color = red)
                Text("VEHICLE WARNING", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold, color = red)
                if (severity != null) Text(severity, Modifier.background(Color(0x1AC73218), RoundedCornerShape(50)).padding(horizontal = 8.dp, vertical = 2.dp), style = MaterialTheme.typography.labelMedium, color = red)
            }
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("$count known issue${if (count == 1) "" else "s"}", Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                TextButton(onShow, Modifier.heightIn(min = 48.dp), colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.onSurface)) { Text("Show", style = MaterialTheme.typography.bodyLarge) }
            }
        }
    }
}

@Composable private fun InfoLine(label: String, modifier: Modifier = Modifier, value: @Composable () -> Unit) {
    Row(modifier.fillMaxWidth().heightIn(min = 32.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        value()
    }
}

/** Web Info tab card: CUSTOMER (name in the accent colour) then JOB INFO rows with values at the right. */
@Composable internal fun MobileInfoCard(job: AutoKeyJobRead, technicians: List<TeamUser>, statusKey: String, severity: String?) {
    val vehicle = listOfNotNull(job.vehicleMake, job.vehicleModel).filter { it.isNotBlank() }.joinToString(" ")
    val valueStyle = MaterialTheme.typography.bodyLarge
    WebCard {
        if (!job.customerName.isNullOrBlank()) Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("CUSTOMER", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant, letterSpacing = 1.sp)
            Text(job.customerName, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.primary)
        }
        Column {
            Text("JOB INFO", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant, letterSpacing = 1.sp)
            HorizontalDivider(Modifier.padding(top = 6.dp, bottom = 4.dp), color = MaterialTheme.colorScheme.outlineVariant)
            InfoLine("Status") { TonePill(statusLabel(statusKey), statusTone(statusKey)) }
            InfoLine("Priority") { Text(job.priority?.replace('_', ' ')?.replaceFirstChar { it.uppercase() } ?: "Normal", style = valueStyle) }
            InfoLine("Created") { Text(formatShopDate(job.createdAt), style = valueStyle) }
            if (vehicle.isNotBlank()) InfoLine("Vehicle") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(vehicle, style = valueStyle)
                    if (severity != null) Text(severity, Modifier.background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(50)).padding(horizontal = 8.dp, vertical = 2.dp), style = MaterialTheme.typography.labelMedium, color = Color(0xFF9B1C1C))
                }
            }
            InfoLine("Qty") { Text(job.keyQuantity.toString(), style = valueStyle) }
            InfoLine("Type") { Text(job.jobType ?: job.title, style = valueStyle) }
            InfoLine("Technician") { Text(technicians.firstOrNull { it.id == job.assignedUserId }?.name ?: if (job.assignedUserId == null) "Unassigned" else "Assigned", style = valueStyle) }
            InfoLine("Scheduled") { Text(job.scheduledAt?.let { formatShopDate(it, TokenStore.calendarTimezone()) } ?: "Unscheduled", style = valueStyle, color = MaterialTheme.colorScheme.primary) }
            if (!job.jobAddress.isNullOrBlank()) InfoLine("Address") { Text(job.jobAddress, style = valueStyle) }
        }
    }
}
