package au.mainspring.nativeapp

import androidx.compose.material3.Text
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.BoardMoveToast
import au.mainspring.nativeapp.ui.screens.BoardMoveToastBar
import au.mainspring.nativeapp.ui.screens.HoldMenuTicket
import org.junit.Assert
import org.junit.Rule
import org.junit.Test

/** Press-and-hold ticket menu: tap opens, hold shows Open job / Move to / Call, reasons are asked for, and the Undo message works. */
class HoldMenuTicketTest {
    @get:Rule val compose = createComposeRule()
    private val targets = listOf("awaiting_quote" to "Awaiting quote", "working_on" to "Working on", "no_go" to "No go")
    private var opened = 0
    private val moves = mutableListOf<Pair<String, String?>>()

    private fun ticket(canMove: Boolean = true, phone: String? = "0400 111 222") {
        compose.setContent { MainspringTheme {
            HoldMenuTicket("Strap replacement", "awaiting_quote", targets, canMove, phone, { opened++ }, { st, why -> moves.add(st to why) }, Modifier_tag()) { Text("Strap replacement") }
        } }
    }
    private fun Modifier_tag() = androidx.compose.ui.Modifier.testTag("ticket")

    @Test fun tapOpensTheJobAndHoldShowsTheMenu() {
        ticket()
        compose.onNodeWithTag("ticket").performClick()
        Assert.assertEquals(1, opened)
        compose.onNodeWithTag("hold-menu").assertDoesNotExist()
        compose.onNodeWithTag("ticket").performTouchInput { longClick() }
        compose.onNodeWithText("Open job").assertExists()
        compose.onNodeWithText("Move to").assertExists()
        compose.onNodeWithText("Call customer").assertExists()
        Assert.assertEquals(1, opened)
    }

    @Test fun moveToListsStagesMarksTheCurrentOneAndMovesInOneTap() {
        ticket()
        compose.onNodeWithTag("ticket").performTouchInput { longClick() }
        compose.onNodeWithTag("hold-move").performClick()
        compose.onNodeWithText("Awaiting quote (now)").assertIsNotEnabled()
        compose.onNodeWithTag("hold-target-working_on").performClick()
        Assert.assertEquals(listOf("working_on" to null), moves)
    }

    @Test fun statusesThatNeedAReasonAskForOneFirst() {
        ticket()
        compose.onNodeWithTag("ticket").performTouchInput { longClick() }
        compose.onNodeWithTag("hold-move").performClick()
        compose.onNodeWithTag("hold-target-no_go").performClick()
        Assert.assertTrue(moves.isEmpty())
        compose.onNodeWithTag("move-reason-confirm").assertIsNotEnabled()
        compose.onNodeWithTag("move-reason").performTextInput("Customer declined the quote")
        compose.onNodeWithTag("move-reason-confirm").performClick()
        Assert.assertEquals(listOf("no_go" to "Customer declined the quote"), moves)
    }

    @Test fun noMoveOrCallWhenReadOnlyOrNoPhone() {
        ticket(canMove = false, phone = null)
        compose.onNodeWithTag("ticket").performTouchInput { longClick() }
        compose.onNodeWithText("Open job").assertExists()
        compose.onNodeWithText("Move to").assertDoesNotExist()
        compose.onNodeWithText("Call customer").assertDoesNotExist()
    }

    @Test fun talkBackHasAMoveToAction() {
        ticket()
        compose.onNodeWithTag("ticket").assert(SemanticsMatcher.keyIsDefined(androidx.compose.ui.semantics.SemanticsProperties.Role))
        val actions = compose.onNodeWithTag("ticket").fetchSemanticsNode().config[androidx.compose.ui.semantics.SemanticsActions.CustomActions]
        Assert.assertTrue(actions.any { it.label == "Move to…" })
    }

    @Test fun undoMessageShowsWhereItMovedAndUndoes() {
        var undone: BoardMoveToast? = null
        compose.setContent { MainspringTheme { BoardMoveToastBar(BoardMoveToast("j1", "awaiting_quote", "working_on", "Working on", queued = true), { undone = it }, {}) } }
        compose.onNodeWithText("Moved to Working on (saved offline, will sync)").assertExists()
        compose.onNodeWithTag("move-undo").performClick()
        Assert.assertEquals("awaiting_quote", undone?.from)
    }
}
