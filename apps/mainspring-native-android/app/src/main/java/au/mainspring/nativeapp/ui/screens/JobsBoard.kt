package au.mainspring.nativeapp.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.Spacer
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
data class BoardCard(val id: String, val title: String, val subtitle: String, val status: String,
    /** Web-style rich card fields (used when [JobsBoard] is called with `web = true`). */
    val number: String? = null, val brand: String? = null, val days: String? = null, val description: String? = null,
    val customerLine: String? = null, val assignee: String? = null, val price: String? = null, val phone: String? = null)

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
    onMoveReason: (id: String, status: String, reason: String?) -> Unit = { id, status, _ -> onMove(id, status) },
    modifier: Modifier = Modifier,
    /** false = natural height (inside a page that scrolls vertically); true = fill the parent and scroll each column. */
    fillHeight: Boolean = true,
    /** Web phone look: bordered white columns with a brown top rule, count badge and rich job cards. */
    web: Boolean = false,
    /** When given, the press-and-hold ticket menu offers "Log work" for that job (web look only). */
    onLogWork: ((String) -> Unit)? = null,
) {
    if(web) { WebBoard(columns, moveTargets, canMove, onOpen, onMoveReason, onMove, modifier, onLogWork); return }
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

private val BoardBrown = Color(0xFF8A6A2F)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun WebBoard(columns: List<BoardColumn>, moveTargets: List<Pair<String, String>>, canMove: Boolean, onOpen: (String) -> Unit,
    onMoveReason: (id: String, status: String, reason: String?) -> Unit, onMove: (id: String, status: String) -> Unit, modifier: Modifier, onLogWork: ((String) -> Unit)? = null) {
    val line = MaterialTheme.colorScheme.outlineVariant
    val square = RoundedCornerShape(2.dp)
    Row(modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 12.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        columns.forEach { col ->
            Surface(Modifier.width(158.dp * (1f + (androidx.compose.ui.platform.LocalDensity.current.fontScale - 1f).coerceAtLeast(0f) * 0.6f)).testTag("board-column-${col.status}"), color = MaterialTheme.colorScheme.surface, shape = square, border = BorderStroke(1.dp, line)) {
                Column {
                    Box(Modifier.fillMaxWidth().height(3.dp).background(BoardBrown))
                    Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(col.label, Modifier.weight(1f), style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold, maxLines = 1)
                        Surface(shape = RoundedCornerShape(50), color = Color(0xFFF5E8D3)) {
                            Text(col.cards.size.toString(), Modifier.padding(horizontal = 6.dp, vertical = 0.dp), style = MaterialTheme.typography.labelMedium, color = BoardBrown)
                        }
                    }
                    HorizontalDivider(color = line)
                    Column(Modifier.padding(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        if(col.cards.isEmpty()) Text("No jobs in ${col.label}", Modifier.fillMaxWidth().padding(vertical = 8.dp), style = MaterialTheme.typography.bodySmall,
                            fontStyle = FontStyle.Italic, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                        col.cards.forEach { card ->
                            var menu by remember(card.id, card.status) { mutableStateOf(false) }
                            HoldMenuTicket(card.title, card.status, moveTargets, canMove, card.phone, { onOpen(card.id) }, { st, why -> onMoveReason(card.id, st, why) }, onLogWork = onLogWork?.let { f -> { f(card.id) } }) {
Surface(Modifier.fillMaxWidth().testTag("board-card-${card.id}"), color = MaterialTheme.colorScheme.surface, shape = square, border = BorderStroke(1.dp, line)) {
                                Column(Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        card.number?.let { Text("#$it", style = MaterialTheme.typography.labelMedium, color = BoardBrown, fontWeight = FontWeight.SemiBold) }
                                        Spacer(Modifier.weight(1f))
                                        card.days?.let { Surface(shape = RoundedCornerShape(50), color = Color(0xFFE3F3E6)) {
                                            Text(it, Modifier.padding(horizontal = 8.dp, vertical = 1.dp), style = MaterialTheme.typography.labelSmall, color = Color(0xFF2E6B3A)) } }
                                    }
                                    card.brand?.takeIf { it.isNotBlank() }?.let { Text(it.uppercase(), style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis) }
                                    Text(card.title, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                    card.customerLine?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis) }
                                    Box {
                                        Surface(onClick = { if(canMove) menu = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 32.dp).testTag("board-move-${card.id}"), shape = square,
                                            color = MaterialTheme.colorScheme.surface, border = BorderStroke(1.dp, MaterialTheme.colorScheme.onSurface)) {
                                            Row(Modifier.padding(horizontal = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                                                Text(columns.firstOrNull { it.status == card.status }?.label ?: card.status, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                                Text("▾", style = MaterialTheme.typography.bodySmall)
                                            }
                                        }
                                        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                                            moveTargets.filter { it.first != card.status }.forEach { (status, label) ->
                                                DropdownMenuItem(text = { Text(label) }, onClick = { menu = false; onMove(card.id, status) }, modifier = Modifier.testTag("board-target-${card.id}-$status"))
                                            }
                                        }
                                    }
                                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                        Text(card.assignee.orEmpty(), Modifier.weight(1f), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                        card.price?.let { Text(it, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold) }
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
