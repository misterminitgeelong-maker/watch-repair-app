package au.mainspring.nativeapp

import au.mainspring.nativeapp.ui.screens.moreTools
import org.junit.Assert.*
import org.junit.Test

class IntegrationVisibilityTest {
    @Test fun shopOwnerAndManagerToolsDoNotIncludeIntegrationManagement() {
        for(teamOwner in listOf(false, true)) {
            val items = moreTools(setOf("watch", "shoe"), owner = true, teamOwner = teamOwner)
            val routes = items.flatMap { listOf(it.route) + it.children.map { child -> child.route } }
            assertFalse("integrations" in routes)
            if(teamOwner) { assertTrue("team" in routes); assertTrue("shopSettings" in routes) }
        }
    }
    @Test fun onlyServerHqCapabilityAddsTheIntegrationTool() {
        val shop = moreTools(setOf("watch"), owner = true, integrationsAllowed = true).single { it.route == "toolsShop" }
        assertEquals(1, shop.children.count { it.route == "integrations" })
    }
}
