package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
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
import au.mainspring.nativeapp.ui.screens.InboxScreen
import au.mainspring.nativeapp.ui.screens.InvoiceDetailScreen
import au.mainspring.nativeapp.ui.screens.InvoicesScreen
import au.mainspring.nativeapp.ui.screens.JobDetailScreen
import au.mainspring.nativeapp.ui.screens.JobsScreen
import au.mainspring.nativeapp.ui.screens.WatchIntakeScreen
import au.mainspring.nativeapp.ui.screens.JobQuotesScreen
import au.mainspring.nativeapp.ui.screens.CustomerEditorScreen
import au.mainspring.nativeapp.ui.screens.ShoeIntakeScreen
import au.mainspring.nativeapp.ui.screens.MobileIntakeScreen
import au.mainspring.nativeapp.ui.screens.MessageThreadScreen
import au.mainspring.nativeapp.ui.screens.MobileFinanceScreen
import au.mainspring.nativeapp.ui.screens.MobileEditorScreen
import au.mainspring.nativeapp.ui.screens.ToolkitScreen
import au.mainspring.nativeapp.ui.screens.ProspectsScreen
import au.mainspring.nativeapp.ui.screens.BookingRequestsScreen
import au.mainspring.nativeapp.ui.screens.WorkLogsScreen
import au.mainspring.nativeapp.ui.screens.CounterEditorScreen
import au.mainspring.nativeapp.ui.screens.CounterSaleScreen
import au.mainspring.nativeapp.ui.screens.DispatchPoolScreen
import au.mainspring.nativeapp.ui.screens.BusinessAccountsScreen
import au.mainspring.nativeapp.ui.screens.BusinessAccountScreen
import au.mainspring.nativeapp.ui.screens.JobPhotosScreen
import au.mainspring.nativeapp.ui.screens.BusinessAccountEditorScreen
import au.mainspring.nativeapp.ui.screens.ArrivalMessageScreen
import au.mainspring.nativeapp.ui.screens.QuoteDetailScreen
import au.mainspring.nativeapp.ui.screens.QuotesScreen
import au.mainspring.nativeapp.ui.screens.ShoeJobDetailScreen
import au.mainspring.nativeapp.ui.screens.ShoeJobsScreen
import kotlinx.coroutines.launch

private val bottomDestinations = setOf("home", "today", "dispatch", "jobs", "watch_jobs", "people", "customers", "inbox", "leads", "more", "route", "dispatchPool", "counterSale", "reports", "stock", "auto_jobs", "quotes", "invoices", "shoe_jobs", "new_intake")

/** Which of the five Atelier tabs a route belongs to. */
private fun tabFor(route: String?) = when(route) {
    "today", "home", "dispatch", "route", "dispatchPool", "new_intake" -> "today"
    "jobs", "watch_jobs", "shoe_jobs", "auto_jobs", "quotes", "invoices", "counterSale" -> "jobs"
    "people", "customers" -> "people"
    "inbox", "leads" -> "inbox"
    else -> "more"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainspringAppShell(
    sessionSummary: String?,
    apiBaseUrl: String,
    onLogout: () -> Unit,
    features: Set<String>,
    sites: List<au.mainspring.nativeapp.api.SessionSite> = emptyList(),
    activeSiteId: String? = null,
    onSwitchSite: (String) -> Unit = {},
    sessionError: String? = null,
) {
    val navController = rememberNavController()
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val showBottomBar = currentRoute in bottomDestinations
    val fieldPreference by DesignPreferences.fieldNavigation.collectAsState()
    val fieldMode = "auto_key" in features && (fieldPreference || !au.mainspring.nativeapp.TokenStore.canManageInvoices())
    val startRoute = "today"
    val canWatch = "watch" in features
    var switchOpen by remember { mutableStateOf(false) }
    val selectedSite = sites.firstOrNull { it.tenantId == activeSiteId }
    val todayContent: @Composable () -> Unit = {
        au.mainspring.nativeapp.ui.screens.TodayHubScreen(features, selectedSite?.name,
            onNewIntake = { navController.navigate("new_intake") },
            onOpenJob = { navController.navigate(au.mainspring.nativeapp.ui.screens.hubJobRoute(it)) },
            onViewAll = { navController.navigate("jobs") { launchSingleTop = true } },
            onOpenQuotes = { navController.navigate("quotes") { launchSingleTop = true } },
            onOpenInvoices = { navController.navigate("invoices") { launchSingleTop = true } },
            onOpenRoute = { navController.navigate(it) { launchSingleTop = true } })
    }
    val jobsContent: @Composable () -> Unit = {
        au.mainspring.nativeapp.ui.screens.AtelierJobsScreen(features, selectedSite?.name,
            onOpenJob = { navController.navigate(au.mainspring.nativeapp.ui.screens.hubJobRoute(it)) },
            onNew = { navController.navigate("new_intake") })
    }
    val peopleContent: @Composable () -> Unit = {
        CustomersScreen(onOpenCustomer = { id -> navController.navigate("customer/$id") }, onNewCustomer = { navController.navigate("newCustomer") })
    }

    run {
        Scaffold(
            contentWindowInsets = androidx.compose.foundation.layout.WindowInsets(0, 0, 0, 0),
            containerColor = MaterialTheme.colorScheme.background,
            bottomBar = {
                if (showBottomBar) {
                    FloatingTabBar(
                        destinations = listOf("today" to "Today", "jobs" to "Jobs", "people" to "People", "inbox" to "Inbox", "more" to "More"),
                        isSelected = { it == tabFor(currentRoute) },
                        onSelect = { route -> navController.navigate(route) { popUpTo(startRoute) { saveState = true }; launchSingleTop = true; restoreState = true } },
                    )
                }
            },
        ) { paddingValues ->
            androidx.compose.foundation.layout.Column(Modifier.padding(paddingValues)) {
            sessionError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) }
            androidx.compose.foundation.layout.Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = androidx.compose.ui.Alignment.TopCenter) {
            NavHost(
                navController = navController,
                startDestination = startRoute,
                modifier = Modifier.widthIn(max = 680.dp).fillMaxHeight().fillMaxWidth(),
            ) {
                composable("today") { todayContent() }
                composable("new_intake") {
                    au.mainspring.nativeapp.ui.screens.NewIntakeScreen(features,
                        onBack = { navController.popBackStack() },
                        onStart = { route -> navController.navigate(route) { popUpTo("new_intake") { inclusive = true } } })
                }
                composable("dispatch") {
                    au.mainspring.nativeapp.ui.screens.DispatchScreen(
                        onOpenJob = { navController.navigate("autoKeyJob/$it") },
                        onNew = { navController.navigate("mobile_intake") },
                        onOpenRoute = { navController.navigate("route") },
                        onOpenPlanner = { navController.navigate("auto_jobs") },
                        onOpenPool = { navController.navigate("dispatchPool") })
                }
                composable("more") { au.mainspring.nativeapp.ui.screens.MoreScreen(selectedSite?.name,sessionSummary,features,sites.size>1,
                    {switchOpen=true},{navController.navigate(it)},onLogout) }
                composable("route") { au.mainspring.nativeapp.ui.screens.RouteScreen({navController.popBackStack()},{navController.navigate("autoKeyJob/$it")}) }
                composable("team") { au.mainspring.nativeapp.ui.screens.TeamScreen({navController.popBackStack()}) }
                composable("leads") { au.mainspring.nativeapp.ui.screens.LeadHubScreen({navController.popBackStack()},{navController.navigate(it)}) }
                composable("home") { todayContent() }
                composable("reports") { au.mainspring.nativeapp.ui.screens.PeriodReportsScreen({ navController.popBackStack() }) }
                composable("stock") { au.mainspring.nativeapp.ui.screens.StockScreen({ navController.popBackStack() }) }
                composable("people") { peopleContent() }
                composable("customers") {
                    CustomersScreen(
                        onOpenCustomer = { id -> navController.navigate("customer/$id") },
                        onNewCustomer = { navController.navigate("newCustomer") },
                    )
                }
                composable("jobs") { jobsContent() }
                composable("watch_jobs") {
                    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Watch repairs") }, navigationIcon = { BackButton({ navController.popBackStack() }) },
                        actions = { au.mainspring.nativeapp.ui.RoundPlusButton({ navController.navigate("watch_intake") }, "New repair", Modifier.padding(end = 12.dp)) }) },
                        containerColor = MaterialTheme.colorScheme.background) { pad ->
                        androidx.compose.foundation.layout.Box(Modifier.padding(pad)) {
                            JobsScreen(onOpenJob = { id -> navController.navigate("watchJob/$id") }, onNewJob = { navController.navigate("watch_intake") })
                        }
                    }
                }
                composable("watch_intake?customerId={customerId}", arguments = listOf(navArgument("customerId") { type = NavType.StringType; nullable = true; defaultValue = null })) { entry ->
                    WatchIntakeScreen(onSwitchService = { key -> navController.navigate(when(key) { "shoe" -> "shoe_intake"; "auto_key" -> "mobile_intake"; else -> "watch_intake" }) { popUpTo("new_intake") { inclusive = false }; launchSingleTop = true } },
                        services = listOfNotNull(if("watch" in features) "watch" to "Watch" else null, if("shoe" in features) "shoe" to "Shoe" else null, if("auto_key" in features) "auto_key" to "Mobile" else null), preselectedCustomerId = entry.arguments?.getString("customerId"), onBack = { navController.popBackStack() }, onOpenJob = { id ->
                        navController.navigate("watchJob/$id") { popUpTo("watch_intake?customerId={customerId}") { inclusive = true } }
                    })
                }
                composable("quotes") {
                    QuotesScreen(
                        onOpenQuote = { id -> navController.navigate("quote/$id") },
                        onBack = { navController.popBackStack() },
                    )
                }
                composable("invoices") {
                    InvoicesScreen(
                        onOpenInvoice = { id -> navController.navigate("invoice/$id") },
                        onBack = { navController.popBackStack() },
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
                        onEdit = { navController.navigate("editCustomer/$it") },
                        onNewRepair = { navController.navigate("watch_intake?customerId=$it") },
                        features = features,
                        onOpenShoeJob = { navController.navigate("shoeJob/$it") },
                        onOpenMobileJob = { navController.navigate("autoKeyJob/$it") },
                        onNewShoe = { navController.navigate("shoe_intake?customerId=$it") },
                        onNewMobile = { navController.navigate("mobile_intake?customerId=$it") },
                        onAddWatch = { navController.navigate("watchEditor/$it") },
                        onEditWatch = { navController.navigate("watchEditor/$id?watchId=$it") },
                    )
                }
                composable("editCustomer/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) { entry ->
                    CustomerEditorScreen(entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() }, onOpenCustomer = { navController.navigate("customer/$it") })
                }
                composable("newCustomer") { CustomerEditorScreen("", onBack = { navController.popBackStack() }, onOpenCustomer = { navController.navigate("customer/$it") { popUpTo("newCustomer") { inclusive = true } } }) }
                composable("watchEditor/{customerId}?watchId={watchId}", arguments = listOf(navArgument("customerId") { type = NavType.StringType }, navArgument("watchId") { type = NavType.StringType; defaultValue = "" })) { entry ->
                    au.mainspring.nativeapp.ui.screens.WatchEditorScreen(entry.arguments?.getString("customerId").orEmpty(), entry.arguments?.getString("watchId").orEmpty(),
                        onBack = { navController.popBackStack() }, onCustomer = { navController.popBackStack() })
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
                        onQuotes = { navController.navigate("jobQuotes/$it") },
                        onMessages = { navController.navigate("messages/repair-jobs/$id") },
                        onWorkLogs = { navController.navigate("workLogs/$id") },
                        onEdit = { navController.navigate("counterEdit/repair-jobs/$id") },
                        onPhotos = { navController.navigate("jobPhotos/repair-jobs/$id") },
                    )
                }
                composable("jobQuotes/{jobId}", arguments = listOf(navArgument("jobId") { type = NavType.StringType })) { entry ->
                    JobQuotesScreen(jobId = entry.arguments?.getString("jobId") ?: return@composable,
                        onBack = { navController.popBackStack() }, onOpenQuote = { navController.navigate("quote/$it") })
                }
                composable("workLogs/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) { entry ->
                    WorkLogsScreen(entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() })
                }
                composable("counterEdit/{resource}/{id}", arguments = listOf(navArgument("resource") { type = NavType.StringType }, navArgument("id") { type = NavType.StringType })) { entry ->
                    CounterEditorScreen(entry.arguments?.getString("resource") ?: return@composable, entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() })
                }
                composable(
                    route = "quote/{quoteId}",
                    arguments = listOf(navArgument("quoteId") { type = NavType.StringType }),
                ) { entry ->
                    val id = entry.arguments?.getString("quoteId") ?: return@composable
                    QuoteDetailScreen(quoteId = id, onBack = { navController.popBackStack() }, onOpenInvoice = { navController.navigate("invoice/$it") })
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
                composable("toolkit") { ToolkitScreen(onBack = { navController.popBackStack() }) }
                composable("prospects") { ProspectsScreen(onBack = { navController.popBackStack() }) }
                composable("bookingRequests") { BookingRequestsScreen(canRequest = "shop_mobile_booking" in features,
                    onBack = { navController.popBackStack() }, onOpenJob = { navController.navigate("autoKeyJob/$it") }) }
                composable("messages/{resource}/{id}", arguments = listOf(navArgument("resource") { type = NavType.StringType }, navArgument("id") { type = NavType.StringType })) { entry ->
                    MessageThreadScreen(entry.arguments?.getString("resource") ?: return@composable,
                        entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() })
                }
                composable("counterSale") { CounterSaleScreen(onBack = { navController.popBackStack() }, onOpenJob = { id,business -> navController.navigate("mobileFinance/$id?business=$business") }) }
                composable("businessAccounts") { BusinessAccountsScreen(onBack = { navController.popBackStack() }, onOpenAccount = { navController.navigate("businessAccount/$it") }, onCreate = { navController.navigate("newBusinessAccount") }) }
                composable("newBusinessAccount") { BusinessAccountEditorScreen("", onBack = { navController.popBackStack() }, onOpenAccount = { navController.navigate("businessAccount/$it") { popUpTo("newBusinessAccount") { inclusive = true } } }) }
                composable("editBusinessAccount/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) { entry ->
                    BusinessAccountEditorScreen(entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() }, onOpenAccount = { navController.popBackStack() })
                }
                composable("businessAccount/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) { entry ->
                    BusinessAccountScreen(entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() },
                        onEdit = { navController.navigate("editBusinessAccount/${entry.arguments?.getString("id")}") },
                        onOpenCustomer = { navController.navigate("customer/$it") }, onOpenJob = { type,id ->
                            when(type) { "watch" -> navController.navigate("watchJob/$id"); "shoe" -> navController.navigate("shoeJob/$id"); "auto_key" -> navController.navigate("autoKeyJob/$id") }
                        })
                }
                composable("dispatchPool") { DispatchPoolScreen(onBack = { navController.popBackStack() },
                    onOpenJob = { navController.navigate("autoKeyJob/$it") }, onOpenBoard = { navController.navigate("auto_jobs") }) }
                composable("shoe_jobs") {
                    ShoeJobsScreen(
                        onBack = { navController.popBackStack() },
                        onOpenJob = { id -> navController.navigate("shoeJob/$id") },
                        onNewJob = { navController.navigate("shoe_intake") },
                    )
                }
                composable("shoe_intake?customerId={customerId}", arguments = listOf(navArgument("customerId") { type = NavType.StringType; nullable = true; defaultValue = null })) { entry ->
                    ShoeIntakeScreen(onSwitchService = { key -> navController.navigate(when(key) { "shoe" -> "shoe_intake"; "auto_key" -> "mobile_intake"; else -> "watch_intake" }) { popUpTo("new_intake") { inclusive = false }; launchSingleTop = true } },
                        services = listOfNotNull(if("watch" in features) "watch" to "Watch" else null, if("shoe" in features) "shoe" to "Shoe" else null, if("auto_key" in features) "auto_key" to "Mobile" else null), preselectedCustomerId = entry.arguments?.getString("customerId"), onBack = { navController.popBackStack() }, onOpenJob = { navController.navigate("shoeJob/$it") { popUpTo("shoe_intake?customerId={customerId}") { inclusive = true } } })
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
                        onMessages = { navController.navigate("messages/shoe-repair-jobs/$id") },
                        onEdit = { navController.navigate("counterEdit/shoe-repair-jobs/$id") },
                        onPhotos = { navController.navigate("jobPhotos/shoe-repair-jobs/$id") },
                    )
                }
                composable("auto_jobs") {
                    au.mainspring.nativeapp.ui.screens.MobileWorkBoardScreen(apiBaseUrl,
                        onBack = { navController.popBackStack() },
                        onOpenJob = { navController.navigate("autoKeyJob/$it") },
                        onNewJob = { navController.navigate("mobile_intake") },
                        onNavigate = { navController.navigate(it) })
                }
                composable("mobile_intake?customerId={customerId}", arguments = listOf(navArgument("customerId") { type = NavType.StringType; nullable = true; defaultValue = null })) { entry ->
                    MobileIntakeScreen(onSwitchService = { key -> navController.navigate(when(key) { "shoe" -> "shoe_intake"; "auto_key" -> "mobile_intake"; else -> "watch_intake" }) { popUpTo("new_intake") { inclusive = false }; launchSingleTop = true } },
                        services = listOfNotNull(if("watch" in features) "watch" to "Watch" else null, if("shoe" in features) "shoe" to "Shoe" else null, if("auto_key" in features) "auto_key" to "Mobile" else null), preselectedCustomerId = entry.arguments?.getString("customerId"), onBack = { navController.popBackStack() }, onOpenJob = { navController.navigate("autoKeyJob/$it") { popUpTo("mobile_intake?customerId={customerId}") { inclusive = true } } })
                }
                composable("mobileFinance/{id}?business={business}", arguments = listOf(navArgument("id") { type = NavType.StringType }, navArgument("business") { type = NavType.BoolType; defaultValue = false })) { entry ->
                    val jobId = entry.arguments?.getString("id") ?: return@composable
                    MobileFinanceScreen(jobId, onBack = { navController.popBackStack() }, businessAccount = entry.arguments?.getBoolean("business") ?: false,
                        onSignature = { navController.navigate("quoteSignature/$jobId/$it") })
                }
                composable("quoteSignature/{jobId}/{quoteId}") { entry ->
                    au.mainspring.nativeapp.ui.screens.QuoteSignatureScreen(entry.arguments?.getString("jobId").orEmpty(), entry.arguments?.getString("quoteId").orEmpty(), { navController.popBackStack() })
                }
                composable("mobileEdit/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) { entry ->
                    MobileEditorScreen(entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() })
                }
                composable("jobPhotos/{resource}/{id}", arguments = listOf(navArgument("resource") { type = NavType.StringType }, navArgument("id") { type = NavType.StringType })) { entry ->
                    JobPhotosScreen(entry.arguments?.getString("resource") ?: return@composable, entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() })
                }
                composable("arrivalMessage/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) { entry ->
                    ArrivalMessageScreen(entry.arguments?.getString("id") ?: return@composable, onBack = { navController.popBackStack() })
                }
                composable(
                    route = "autoKeyJob/{jobId}?initialStatus={initialStatus}",
                    arguments = listOf(navArgument("jobId") { type = NavType.StringType },navArgument("initialStatus") {type=NavType.StringType;nullable=true;defaultValue=null}),
                ) { entry ->
                    val id = entry.arguments?.getString("jobId") ?: return@composable
                    AutoKeyJobDetailScreen(
                        jobId = id,
                        apiBaseUrl = apiBaseUrl,
                        initialStatus = entry.arguments?.getString("initialStatus"),
                        onBack = { navController.popBackStack() },
                        onMessages = { navController.navigate("messages/auto-key-jobs/$id") },
                        onFinance = { navController.navigate("mobileFinance/$id?business=$it") },
                        onEdit = { navController.navigate("mobileEdit/$id") },
                        onPhotos = { navController.navigate("jobPhotos/auto-key-jobs/$id") },
                        onArrival = { navController.navigate("arrivalMessage/$id") },
                        onSignature = { navController.navigate("quoteSignature/$id/$it") },
                    )
                }
            }
            }
            }
        }
    }
    if(switchOpen) androidx.compose.material3.AlertDialog(onDismissRequest = { switchOpen = false }, title = { Text("Switch shop") },
        text = { androidx.compose.foundation.layout.Column(Modifier.verticalScroll(rememberScrollState())) {
            Text("Unsaved drafts remain tied to the shop and account that opened them.")
            sites.forEach { site -> TextButton(onClick = { switchOpen = false; onSwitchSite(site.tenantId) }, enabled = site.tenantId != activeSiteId) { Text(site.name) } }
        } }, confirmButton = { TextButton(onClick = { switchOpen = false }) { Text("Cancel") } })
}

private fun mainTitle(route: String?) = when(route) {
    "home" -> "Home"; "customers" -> "Customers"; "jobs" -> "Watch repairs"
    "quotes" -> "Quotes"; "invoices" -> "Invoices"; else -> "Mainspring"
}
