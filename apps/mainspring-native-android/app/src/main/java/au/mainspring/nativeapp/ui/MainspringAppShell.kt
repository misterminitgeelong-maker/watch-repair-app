package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import au.mainspring.nativeapp.ui.screens.CustomerDetailScreen
import au.mainspring.nativeapp.ui.screens.CustomersScreen
import au.mainspring.nativeapp.ui.screens.DashboardScreen
import au.mainspring.nativeapp.ui.screens.JobsScreen

private val bottomDestinations = setOf("home", "customers", "jobs")

@Composable
fun MainspringAppShell(
    sessionSummary: String?,
    apiBaseUrl: String,
    onLogout: () -> Unit,
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val showBottomBar = currentRoute in bottomDestinations

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    NavigationBarItem(
                        selected = currentRoute == "home",
                        onClick = {
                            navController.navigate("home") { launchSingleTop = true }
                        },
                        icon = { Text("⌂") },
                        label = { Text("Home") },
                    )
                    NavigationBarItem(
                        selected = currentRoute == "customers",
                        onClick = {
                            navController.navigate("customers") { launchSingleTop = true }
                        },
                        icon = { Text("◎") },
                        label = { Text("People") },
                    )
                    NavigationBarItem(
                        selected = currentRoute == "jobs",
                        onClick = {
                            navController.navigate("jobs") { launchSingleTop = true }
                        },
                        icon = { Text("⌚") },
                        label = { Text("Jobs") },
                    )
                }
            }
        },
    ) { paddingValues ->
        NavHost(
            navController = navController,
            startDestination = "home",
            modifier = Modifier.padding(paddingValues),
        ) {
            composable("home") {
                DashboardScreen(
                    sessionSummary = sessionSummary,
                    apiBaseUrl = apiBaseUrl,
                    onLogout = onLogout,
                )
            }
            composable("customers") {
                CustomersScreen(
                    onOpenCustomer = { id -> navController.navigate("customer/$id") },
                )
            }
            composable("jobs") {
                JobsScreen()
            }
            composable(
                route = "customer/{customerId}",
                arguments = listOf(
                    navArgument("customerId") { type = NavType.StringType },
                ),
            ) { entry ->
                val id = entry.arguments?.getString("customerId") ?: return@composable
                CustomerDetailScreen(
                    customerId = id,
                    onBack = { navController.popBackStack() },
                )
            }
        }
    }
}
