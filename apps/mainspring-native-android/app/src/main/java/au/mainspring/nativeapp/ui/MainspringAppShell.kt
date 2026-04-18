package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import au.mainspring.nativeapp.ui.screens.AutoKeyJobDetailScreen
import au.mainspring.nativeapp.ui.screens.AutoKeyJobsScreen
import au.mainspring.nativeapp.ui.screens.CustomerDetailScreen
import au.mainspring.nativeapp.ui.screens.CustomersScreen
import au.mainspring.nativeapp.ui.screens.DashboardScreen
import au.mainspring.nativeapp.ui.screens.InboxScreen
import au.mainspring.nativeapp.ui.screens.InvoiceDetailScreen
import au.mainspring.nativeapp.ui.screens.InvoicesScreen
import au.mainspring.nativeapp.ui.screens.JobDetailScreen
import au.mainspring.nativeapp.ui.screens.JobsScreen
import au.mainspring.nativeapp.ui.screens.QuoteDetailScreen
import au.mainspring.nativeapp.ui.screens.QuotesScreen
import au.mainspring.nativeapp.ui.screens.ShoeJobDetailScreen
import au.mainspring.nativeapp.ui.screens.ShoeJobsScreen
import kotlinx.coroutines.launch

private val bottomDestinations = setOf("home", "customers", "jobs", "quotes", "invoices")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainspringAppShell(
    sessionSummary: String?,
    apiBaseUrl: String,
    onLogout: () -> Unit,
) {
    val navController = rememberNavController()
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val showBottomBar = currentRoute in bottomDestinations
    val showMainTopBar = currentRoute in bottomDestinations

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet(modifier = Modifier.width(300.dp)) {
                Text(
                    "More",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(horizontal = 24.dp, vertical = 16.dp),
                )
                NavigationDrawerItem(
                    label = { Text("Inbox") },
                    selected = currentRoute == "inbox",
                    onClick = {
                        scope.launch { drawerState.close() }
                        navController.navigate("inbox")
                    },
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
                NavigationDrawerItem(
                    label = { Text("Shoe repairs") },
                    selected = currentRoute == "shoe_jobs" || (currentRoute?.startsWith("shoeJob/") == true),
                    onClick = {
                        scope.launch { drawerState.close() }
                        navController.navigate("shoe_jobs")
                    },
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
                NavigationDrawerItem(
                    label = { Text("Mobile services") },
                    selected = currentRoute == "auto_jobs" || (currentRoute?.startsWith("autoKeyJob/") == true),
                    onClick = {
                        scope.launch { drawerState.close() }
                        navController.navigate("auto_jobs")
                    },
                    modifier = Modifier.padding(horizontal = 12.dp),
                )
                Spacer(Modifier.height(16.dp))
            }
        },
    ) {
        Scaffold(
            topBar = {
                if (showMainTopBar) {
                    TopAppBar(
                        title = { Text("Mainspring") },
                        navigationIcon = {
                            TextButton(onClick = { scope.launch { drawerState.open() } }) {
                                Text("Menu")
                            }
                        },
                    )
                }
            },
            bottomBar = {
                if (showBottomBar) {
                    NavigationBar {
                        NavigationBarItem(
                            selected = currentRoute == "home",
                            onClick = { navController.navigate("home") { launchSingleTop = true } },
                            icon = { Text("⌂") },
                            label = { Text("Home") },
                        )
                        NavigationBarItem(
                            selected = currentRoute == "customers",
                            onClick = { navController.navigate("customers") { launchSingleTop = true } },
                            icon = { Text("◎") },
                            label = { Text("People") },
                        )
                        NavigationBarItem(
                            selected = currentRoute == "jobs",
                            onClick = { navController.navigate("jobs") { launchSingleTop = true } },
                            icon = { Text("⌚") },
                            label = { Text("Watch") },
                        )
                        NavigationBarItem(
                            selected = currentRoute == "quotes",
                            onClick = { navController.navigate("quotes") { launchSingleTop = true } },
                            icon = { Text("¶") },
                            label = { Text("Quotes") },
                        )
                        NavigationBarItem(
                            selected = currentRoute == "invoices",
                            onClick = { navController.navigate("invoices") { launchSingleTop = true } },
                            icon = { Text("I") },
                            label = { Text("Invoices") },
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
                        onOpenWatchJobs = { navController.navigate("jobs") { launchSingleTop = true } },
                        onOpenQuotes = { navController.navigate("quotes") { launchSingleTop = true } },
                        onOpenInvoices = { navController.navigate("invoices") { launchSingleTop = true } },
                        onOpenShoeJobs = {
                            navController.navigate("shoe_jobs") { launchSingleTop = true }
                        },
                        onOpenAutoJobs = {
                            navController.navigate("auto_jobs") { launchSingleTop = true }
                        },
                        onOpenAutoJob = { jobId -> navController.navigate("autoKeyJob/$jobId") },
                    )
                }
                composable("customers") {
                    CustomersScreen(
                        onOpenCustomer = { id -> navController.navigate("customer/$id") },
                    )
                }
                composable("jobs") {
                    JobsScreen(
                        onOpenJob = { id -> navController.navigate("watchJob/$id") },
                    )
                }
                composable("quotes") {
                    QuotesScreen(
                        onOpenQuote = { id -> navController.navigate("quote/$id") },
                    )
                }
                composable("invoices") {
                    InvoicesScreen(
                        onOpenInvoice = { id -> navController.navigate("invoice/$id") },
                    )
                }
                composable(
                    route = "customer/{customerId}",
                    arguments = listOf(navArgument("customerId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("customerId") ?: return@composable
                    CustomerDetailScreen(
                        customerId = id,
                        onBack = { navController.popBackStack() },
                        onOpenWatchJob = { jobId -> navController.navigate("watchJob/$jobId") },
                    )
                }
                composable(
                    route = "watchJob/{jobId}",
                    arguments = listOf(navArgument("jobId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("jobId") ?: return@composable
                    JobDetailScreen(
                        jobId = id,
                        apiBaseUrl = apiBaseUrl,
                        onBack = { navController.popBackStack() },
                    )
                }
                composable(
                    route = "quote/{quoteId}",
                    arguments = listOf(navArgument("quoteId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("quoteId") ?: return@composable
                    QuoteDetailScreen(quoteId = id, onBack = { navController.popBackStack() })
                }
                composable(
                    route = "invoice/{invoiceId}",
                    arguments = listOf(navArgument("invoiceId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("invoiceId") ?: return@composable
                    InvoiceDetailScreen(invoiceId = id, onBack = { navController.popBackStack() })
                }
                composable("inbox") {
                    InboxScreen(onBack = { navController.popBackStack() })
                }
                composable("shoe_jobs") {
                    ShoeJobsScreen(
                        onBack = { navController.popBackStack() },
                        onOpenJob = { id -> navController.navigate("shoeJob/$id") },
                    )
                }
                composable(
                    route = "shoeJob/{jobId}",
                    arguments = listOf(navArgument("jobId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("jobId") ?: return@composable
                    ShoeJobDetailScreen(
                        jobId = id,
                        apiBaseUrl = apiBaseUrl,
                        onBack = { navController.popBackStack() },
                    )
                }
                composable("auto_jobs") {
                    AutoKeyJobsScreen(
                        onBack = { navController.popBackStack() },
                        onOpenJob = { id -> navController.navigate("autoKeyJob/$id") },
                    )
                }
                composable(
                    route = "autoKeyJob/{jobId}",
                    arguments = listOf(navArgument("jobId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("jobId") ?: return@composable
                    AutoKeyJobDetailScreen(
                        jobId = id,
                        apiBaseUrl = apiBaseUrl,
                        onBack = { navController.popBackStack() },
                    )
                }
            }
        }
    }
}
