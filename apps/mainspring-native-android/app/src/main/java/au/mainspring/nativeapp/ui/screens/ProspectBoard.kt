package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.PROSPECT_STAGES
import au.mainspring.nativeapp.api.ProspectLead
import au.mainspring.nativeapp.prospectCards
import au.mainspring.nativeapp.prospectNextStage

/** Prospect kanban: one column per stage. The backend only supports advancing one stage, so each card offers "Mark as ..." rather than free moves. */
@Composable
internal fun ProspectBoard(leads: List<ProspectLead>, canMove: Boolean, onOpen: (String) -> Unit, onAdvance: (ProspectLead) -> Unit) {
    fun stageLabel(s: String) = PROSPECT_STAGES.firstOrNull { it.first == s }?.second ?: au.mainspring.nativeapp.ui.statusLabel(s)
    val columns = buildBoardColumns(prospectCards(leads), PROSPECT_STAGES.map { it.first }, ::stageLabel)
    Row(Modifier.fillMaxWidth().height(460.dp).horizontalScroll(rememberScrollState()).testTag("prospects-board"), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        columns.forEach { col ->
            Column(Modifier.width(260.dp).fillMaxHeight().testTag("prospect-column-${col.status}")) {
                Text("${col.label} (${col.cards.size})", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(bottom = 8.dp))
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (col.cards.isEmpty()) Text("Nothing here", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    col.cards.forEach { card ->
                        val lead = leads.first { it.id == card.id }
                        val next = prospectNextStage(lead.status)
                        Surface(Modifier.fillMaxWidth().testTag("prospect-card-${card.id}"), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
                            Column(Modifier.clickable(role = Role.Button) { onOpen(card.id) }.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(card.title, style = MaterialTheme.typography.titleSmall)
                                if (card.subtitle.isNotBlank()) Text(card.subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                if (next != null) TextButton(onClick = { onAdvance(lead) }, enabled = canMove, modifier = Modifier.heightIn(min = 48.dp).testTag("prospect-advance-${card.id}")) {
                                    Text("Mark as " + stageLabel(next))
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
