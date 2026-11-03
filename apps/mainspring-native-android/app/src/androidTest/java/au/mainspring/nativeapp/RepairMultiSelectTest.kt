package au.mainspring.nativeapp

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.RepairMultiSelect
import au.mainspring.nativeapp.ui.RepairOption
import org.junit.Rule
import org.junit.Test

class RepairMultiSelectTest {
    @get:Rule val compose = createComposeRule()

    private val options = listOf(
        RepairOption("battery", "Battery replacement", 4500, "$45.00"),
        RepairOption("band", "Band resize", 2000, "$20.00"),
        RepairOption("crystal", "Crystal fit", 7500, "$75.00"),
    )

    @Test fun openSearchSelectTwoThenDeselectOne() {
        compose.setContent {
            MainspringTheme {
                var selected by androidx.compose.runtime.saveable.rememberSaveable { mutableStateOf(emptySet<String>()) }
                RepairMultiSelect(options, selected, { k -> selected = if(k in selected) selected - k else selected + k },
                    totalCents = options.filter { it.key in selected }.sumOf { it.priceCents ?: 0 }.takeIf { selected.isNotEmpty() })
            }
        }
        compose.onNodeWithTag("repair-select-field").assertTextContains("Select repairs (optional)")
        compose.onNodeWithTag("repair-select-field").performClick()
        compose.onNodeWithTag("repair-search").performTextInput("b")
        compose.onNodeWithTag("repair-option-crystal").assertDoesNotExist()
        compose.onNodeWithTag("repair-option-battery").performClick()
        compose.onNodeWithTag("repair-option-band").performClick()
        compose.onNodeWithTag("repair-done").performClick()
        compose.onNodeWithTag("repair-select-field").assertTextContains("2 repairs · ${au.mainspring.nativeapp.ui.formatCents(6500, "AUD")}")
        compose.onNodeWithTag("repair-chip-battery").assertExists()
        compose.onNodeWithTag("repair-chip-band").assertExists()
        compose.onNodeWithTag("repair-total").assertTextContains("Total: ${au.mainspring.nativeapp.ui.formatCents(6500, "AUD")}")
        compose.onNodeWithTag("repair-chip-battery").performClick()
        compose.onNodeWithTag("repair-chip-battery").assertDoesNotExist()
        compose.onNodeWithTag("repair-select-field").assertTextContains("1 repair · ${au.mainspring.nativeapp.ui.formatCents(2000, "AUD")}")
    }
}
