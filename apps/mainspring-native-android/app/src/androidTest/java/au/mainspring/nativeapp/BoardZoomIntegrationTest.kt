package au.mainspring.nativeapp

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.pinch
import androidx.compose.ui.unit.dp
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.BoardCard
import au.mainspring.nativeapp.ui.screens.BoardZoomMemory
import au.mainspring.nativeapp.ui.screens.JobsBoard
import au.mainspring.nativeapp.ui.screens.WebKanban
import au.mainspring.nativeapp.ui.screens.WebKanbanColumn
import au.mainspring.nativeapp.ui.screens.ZoomableBoard
import au.mainspring.nativeapp.ui.screens.buildBoardColumns
import org.junit.After
import org.junit.Assert
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/** The real Watch board and the Shoe/Mobile kanban inside the zoom wrapper, pinched with two moving fingers and a real lift. */
class BoardZoomIntegrationTest {
    @get:Rule val compose = createComposeRule()
    private var opened = ""

    @Before fun setup() { BoardZoomMemory.clear(); opened = "" }
    @After fun cleanup() { BoardZoomMemory.clear() }

    private fun pillPercent(): Int {
        val text = compose.onNodeWithTag("zoom-reset").fetchSemanticsNode().config[androidx.compose.ui.semantics.SemanticsProperties.Text].joinToString("") { it.text }
        return Regex("(\\d+)%").find(text)!!.groupValues[1].toInt()
    }
    private fun pinch(tag: String, startGap: Float, endGap: Float) = compose.onNodeWithTag(tag).performTouchInput {
        pinch(Offset(center.x - startGap / 2, centerY), Offset(center.x - endGap / 2, centerY), Offset(center.x + startGap / 2, centerY), Offset(center.x + endGap / 2, centerY), durationMillis = 600)
    }

    private val statuses = listOf("awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on", "awaiting_parts", "completed", "awaiting_collection", "collected")
    private fun cards() = statuses.mapIndexed { i, st -> BoardCard("j$i", "Job $i", "J$i", st, number = "JOB-$i", brand = "Seiko", customerLine = "Customer $i", price = "$90.00") }

    private fun checkZooms(tag: String) {
        compose.onNodeWithTag("zoom-reset").assertDoesNotExistCompat()
        pinch(tag, 400f, 40f); compose.waitForIdle()
        val out = pillPercent()
        Assert.assertTrue("zoomed out to fit every column (was $out%)", out in 20..75)
        Thread.sleep(400); Assert.assertEquals("stays after the fingers lift", out, pillPercent())
        compose.onNodeWithTag("zoom-reset").performClick()
        compose.onNodeWithTag("zoom-reset").assertDoesNotExistCompat()
        pinch(tag, 60f, 500f); compose.waitForIdle()
        val inn = pillPercent()
        Assert.assertTrue("zoomed in to about 2x (was $inn%)", inn in 150..200)
        Thread.sleep(400); Assert.assertEquals(inn, pillPercent())
    }
    private fun androidx.compose.ui.test.SemanticsNodeInteraction.assertDoesNotExistCompat() = assertDoesNotExist()

    @Test fun watchBoardZoomsOutToFitAndInToTwoTimes() {
        compose.setContent { MainspringTheme { Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())) {
            ZoomableBoard("watch", statuses.size, 158.dp) {
                JobsBoard(buildBoardColumns(cards(), statuses) { it }, statuses.map { it to it }, canMove = true, onOpen = { opened = it }, onMove = { _, _ -> }, fillHeight = false, web = true)
            }
        } } }
        checkZooms("zoom-board-watch")
    }

    @Test fun shoeAndMobileKanbanZoomsOutToFitAndInToTwoTimes() {
        val columns = statuses.map { st -> WebKanbanColumn(st, st, Color(0xFF9A5F10), Color(0xFFFAEEDB), cards().filter { it.status == st }) }
        compose.setContent { MainspringTheme { Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())) {
            ZoomableBoard("shoe", columns.size, 168.dp) { WebKanban(columns) { card, _ -> Text(card.title, Modifier.fillMaxWidth()) } }
        } } }
        checkZooms("zoom-board-shoe")
    }

    @Test fun tappingATicketStillOpensItAfterZooming() {
        compose.setContent { MainspringTheme { Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())) {
            ZoomableBoard("watch", statuses.size, 158.dp) {
                JobsBoard(buildBoardColumns(cards(), statuses) { it }, statuses.map { it to it }, canMove = true, onOpen = { opened = it }, onMove = { _, _ -> }, fillHeight = false, web = true)
            }
        } } }
        pinch("zoom-board-watch", 60f, 300f); compose.waitForIdle()
        // the ticket is a single merged node (tap or hold), so look for the tag in the unmerged tree
        compose.onNodeWithTag("board-card-j0", useUnmergedTree = true).performClick()
        Assert.assertEquals("j0", opened)
    }
}
