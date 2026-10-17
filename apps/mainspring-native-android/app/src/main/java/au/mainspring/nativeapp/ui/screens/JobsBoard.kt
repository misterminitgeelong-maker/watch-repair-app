package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

/** One card on a status board. */
data class BoardCard(val id: String, val title: String, val subtitle: String, val status: String)

/** One status column; [cards] are already filtered and sorted. */
data class BoardColumn(val status: String, val label: String, val cards: List<BoardCard>)

/**
 * Status board (web kanban) for watch and shoe jobs: one column per status, scrolled sideways.
 * Cards open the job; "Move to" changes status in one tap through [onMove] (no drag on a phone).
 */
@Composable
fun JobsBoard(
    columns: List<BoardColumn>,
    moveTargets: List<Pair<String, String>>,
    canMove: Boolean,
    onOpen: (String) -> Unit,
    onMove: (id: String, status: String) -> Unit,
    modifier: Modifier = Modifier,
    /** false = natural height (inside a page that scrolls vertically); true = fill the parent and scroll each column. */
    fillHeight: Boolean = true,
) {
    val calibre = au.mainspring.nativeapp.ui.LocalCalibre.current
    Row((if(fillHeight) modifier.fillMaxHeight() else modifier).horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        columns.forEach { col ->
            Column((if(fillHeight) Modifier.width(260.dp).fillMaxHeight() else Modifier.width(260.dp)).testTag("board-column-${col.status}")) {
                Text("${col.label} (${col.cards.size})", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(bottom = 8.dp))
                Column(if(fillHeight) Modifier.verticalScroll(rememberScrollState()) else Modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (col.cards.isEmpty()) Text("Nothing here", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    col.cards.forEach { card ->
                        var menu by remember(card.id, card.status) { mutableStateOf(false) }
                        Surface(Modifier.fillMaxWidth().testTag("board-card-${card.id}"), color = MaterialTheme.colorScheme.surface, shape = MaterialTheme.shapes.medium) {
                            Column(Modifier.clickable(role = androidx.compose.ui.semantics.Role.Button) { onOpen(card.id) }.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(card.title, style = MaterialTheme.typography.titleSmall)
                                Text(card.subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                if (canMove) {
                                    TextButton(onClick = { menu = true }, modifier = Modifier.heightIn(min = 48.dp).testTag("board-move-${card.id}")) { Text("Move to…") }
                                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                                        moveTargets.filter { it.first != card.status }.forEach { (status, label) ->
                                            DropdownMenuItem(text = { Text(label) }, onClick = { menu = false; onMove(card.id, status) },
                                                modifier = Modifier.testTag("board-target-${card.id}-$status"))
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

/** Groups cards into columns following [order]; statuses outside [order] get their own trailing column. */
fun buildBoardColumns(cards: List<BoardCard>, order: List<String>, label: (String) -> String): List<BoardColumn> {
    val byStatus = cards.groupBy { it.status }
    val extra = byStatus.keys.filter { it !in order }
    return (order + extra).map { BoardColumn(it, label(it), byStatus[it].orEmpty()) }
}
