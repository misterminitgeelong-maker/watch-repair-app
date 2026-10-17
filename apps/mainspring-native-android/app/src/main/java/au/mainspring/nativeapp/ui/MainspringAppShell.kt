package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
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
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.statusBarsPadding
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

private val bottomDestinations = setOf("toolsWorkshop", "toolsMobile", "toolsShop", "home", "today", "dispatch", "jobs", "watch_jobs", "people", "customers", "inbox", "leads", "more", "route", "dispatchPool", "counterSale", "reports", "stock", "auto_jobs", "quotes", "invoices", "shoe_jobs", "new_intake")

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
    subscriptionStatus: String? = null,
    trialEnd: String? = null,
    sessionRole: String? = null,
) {
    val navController = rememberNavController()
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    val showBottomBar = currentRoute in bottomDestinations
    androidx.compose.runtime.DisposableEffect(Unit) { au.mainspring.nativeapp.InboxCountStore.start(); onDispose { au.mainspring.nativeapp.InboxCountStore.stop() } }
    val routeArgId = navBackStackEntry?.arguments?.getString("jobId")
    androidx.compose.runtime.LaunchedEffect(currentRoute, routeArgId) {
        val base = currentRoute?.substringBefore("/{")
        if(routeArgId != null && base != null) au.mainspring.nativeapp.ui.RecentItems.record("$base/$routeArgId")
    }
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
        val paneWide = androidx.compose.ui.platform.LocalConfiguration.current.screenWidthDp >= 840 && au.mainspring.nativeapp.ui.LocalCalibre.current
        var selected by androidx.compose.runtime.saveable.rememberSaveable { androidx.compose.runtime.mutableStateOf<Pair<String, String>?>(null) }
        if(!paneWide) au.mainspring.nativeapp.ui.screens.AtelierJobsScreen(features, selectedSite?.name,
            onOpenJob = { navController.navigate(au.mainspring.nativeapp.ui.screens.hubJobRoute(it)) },
            onNew = { navController.navigate("new_intake") })
        else androidx.compose.foundation.layout.Row(Modifier.fillMaxSize()) {
            androidx.compose.foundation.layout.Box(Modifier.weight(0.42f)) {
                au.mainspring.nativeapp.ui.screens.AtelierJobsScreen(features, selectedSite?.name,
                    onOpenJob = { job -> if(job.service == "watch" || job.service == "shoe") selected = job.service to job.id else navController.navigate(au.mainspring.nativeapp.ui.screens.hubJobRoute(job)) },
                    onNew = { navController.navigate("new_intake") })
            }
            androidx.compose.material3.VerticalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            androidx.compose.foundation.layout.Box(Modifier.weight(0.58f)) {
                val sel = selected
                if(sel == null) androidx.compose.foundation.layout.Column(Modifier.fillMaxSize().padding(32.dp), verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center, horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                    au.mainspring.nativeapp.ui.MonoLabel("Select a job")
                    Text("Choose a repair from the list to see its record here.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else androidx.compose.runtime.key(sel) {
                    if(sel.first == "watch") au.mainspring.nativeapp.ui.screens.JobDetailScreen(jobId = sel.second, apiBaseUrl = apiBaseUrl, onBack = { selected = null },
                        onQuotes = { navController.navigate("jobQuotes/$it") }, onMessages = { navController.navigate("messages/repair-jobs/${sel.second}") },
                        onWorkLogs = { navController.navigate("workLogs/${sel.second}") }, onEdit = { navController.navigate("counterEdit/repair-jobs/${sel.second}") },
                        onPhotos = { navController.navigate("jobPhotos/repair-jobs/${sel.second}") },
                        onDeleted = { selected = null }, onDuplicated = { navController.navigate("watchJob/$it") }, onEditCustomer = { navController.navigate("editCustomer/$it") },
                        onEditWatch = { c, w -> navController.navigate("watchEditor/$c?watchId=$w") })
                    else au.mainspring.nativeapp.ui.screens.ShoeJobDetailScreen(jobId = sel.second, apiBaseUrl = apiBaseUrl, onBack = { selected = null },
                        onMessages = { navController.navigate("messages/shoe-repair-jobs/${sel.second}") }, onEdit = { navController.navigate("counterEdit/shoe-repair-jobs/${sel.second}") },
                        onPhotos = { navController.navigate("jobPhotos/shoe-repair-jobs/${sel.second}") },
                        onDeleted = { selected = null }, onDuplicated = { navController.navigate("shoeJob/$it") }, onEditCustomer = { navController.navigate("editCustomer/$it") })
                }
            }
        }
    }
    val peopleContent: @Composable () -> Unit = {
        CustomersScreen(onOpenCustomer = { id -> navController.navigate("customer/$id") }, onNewCustomer = { navController.navigate("newCustomer") })
    }

    val wide = androidx.compose.ui.platform.LocalConfiguration.current.screenWidthDp >= 840 && au.mainspring.nativeapp.ui.LocalCalibre.current
    run {
        Scaffold(
            contentWindowInsets = androidx.compose.foundation.layout.WindowInsets(0, 0, 0, 0),
            containerColor = MaterialTheme.colorScheme.background,
            topBar = {
                if (showBottomBar && !wide) AppHeader({ navController.navigate("search") { launchSingleTop = true } })
                else if (wide && showBottomBar) androidx.compose.foundation.layout.Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.background)) {
                    androidx.compose.foundation.layout.Row(Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 32.dp, vertical = 12.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(28.dp)) {
                        androidx.compose.foundation.layout.Box(Modifier.weight(1f)) { au.mainspring.nativeapp.ui.CalibreWordmark(selectedSite?.name, Modifier.padding(0.dp), null) }
                        navTabs(features).forEach { (key, label) ->
                            au.mainspring.nativeapp.ui.PillChip(label, tabFor(currentRoute, features) == key, { navController.navigate(tabRoute(key)) { popUpTo(startRoute) { saveState = true }; launchSingleTop = true; restoreState = true } }, Modifier.testTag("nav-$key"))
                        }
                        SearchIconButton({ navController.navigate("search") { launchSingleTop = true } })
                    }
                    androidx.compose.material3.HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                }
            },
            bottomBar = {
                if (showBottomBar && !wide) {
                    FloatingTabBar(
                        destinations = navTabs(features),
                        isSelected = { it == tabFor(currentRoute, features) },
                        onSelect = { key -> navController.navigate(tabRoute(key)) { popUpTo(startRoute) { saveState = true }; launchSingleTop = true; restoreState = true } },
                    )
                }
            },
        ) { paddingValues ->
            androidx.compose.foundation.layout.Column(Modifier.padding(paddingValues).then(if(showBottomBar && !wide) Modifier.consumeWindowInsets(WindowInsets.statusBars) else Modifier)) {
            var bannerShowing by remember { mutableStateOf(false) }
            au.mainspring.nativeapp.ui.ConnectivityBanner(onOpenQueue = { navController.navigate("queuedChanges") }, onVisibleChange = { bannerShowing = it })
            au.mainspring.nativeapp.ui.SubscriptionBanner(subscriptionStatus, trialEnd, sessionRole)
            sessionError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it, Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) }
            androidx.compose.foundation.layout.Box(Modifier.weight(1f).fillMaxWidth().then(if(bannerShowing) Modifier.consumeWindowInsets(WindowInsets.statusBars) else Modifier), contentAlignment = androidx.compose.ui.Alignment.TopCenter) {
            au.mainspring.nativeapp.ui.screens.AcceptBookingLinkEffect { route -> navController.navigate(route) }
            NavHost(
                navController = navController,
                startDestination = startRoute,
                modifier = Modifier.widthIn(max = if(wide) 1280.dp else 680.dp).fillMaxHeight().fillMaxWidth(),
            ) {
                composable("today") { todayContent() }
                composable("new_intake") {
                    au.mainspring.nativeapp.ui.screens.NewIntakeScreen(features,
                        onBack = { navController.popBackStack() },
                        onStart = { route -> navController.navigate(route) { popUpTo("new_intake") { inclusive = true } } })
                }
                composable("dispatch") {
                    au.mainspring.nativeapp.ui.screens.DispatchScreen(
                        onOpenBookingRequests = { navController.navigate("bookingRequests") },
                        onOpenJob = { navController.navigate("autoKeyJob/$it") },
                        onNew = { navController.navigate("mobile_intake") },
                        onOpenRoute = { navController.navigate("route") },
                        onOpenPlanner = { navController.navigate("auto_jobs") },
                        onOpenPool = { navController.navigate("dispatchPool") })
                }
                listOf("toolsWorkshop", "toolsMobile", "toolsShop").forEach { key ->
                    composable(key) { au.mainspring.nativeapp.ui.screens.ToolsGridScreen(key, features, { navController.popBackStack() }, { navController.navigate(it) }) }
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
                    JobsScreen(onOpenJob = { id -> navController.navigate("watchJob/$id") }, onNewJob = { navController.navigate("watch_intake") },
                        onOpenQueue = { navController.navigate("repairQueue") })
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
                        onOpenMobileInvoice = { jobId -> navController.navigate("mobileFinance/$jobId") },
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
                        onDeleted = { navController.popBackStack() },
                        onDuplicated = { navController.navigate("watchJob/$it") },
                        onEditCustomer = { navController.navigate("editCustomer/$it") },
                        onEditWatch = { c, w -> navController.navigate("watchEditor/$c?watchId=$w") },
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
                    InboxScreen(onBack = { navController.popBackStack() }, onOpenEntity = { navController.navigate(it) })
                }
                composable("toolkit") { ToolkitScreen(onBack = { navController.popBackStack() }) }
                composable("prospects") { ProspectsScreen(onBack = { navController.popBackStack() }) }
                composable("revenueControl") { au.mainspring.nativeapp.ui.screens.RevenueControlScreen(onBack = { navController.popBackStack() }, onOpenJob = { navController.navigate("autoKeyJob/$it") }) }
                composable("queuedChanges") { au.mainspring.nativeapp.ui.screens.QueuedChangesScreen { navController.popBackStack() } }
                composable("shopSettings") { au.mainspring.nativeapp.ui.screens.OwnerSettingsScreen(onBack = { navController.popBackStack() }) }
                composable("reportExtras") { au.mainspring.nativeapp.ui.screens.ReportExtrasScreen(onBack = { navController.popBackStack() }) }
                composable("repairQueue") { au.mainspring.nativeapp.ui.screens.RepairQueueScreen(onBack = { navController.popBackStack() }, onOpenJob = { navController.navigate("watchJob/$it") }, onOpenShoeJob = { navController.navigate("shoeJob/$it") }) }
                composable(au.mainspring.nativeapp.BookingDeepLink.ROUTE_PATTERN) { e -> au.mainspring.nativeapp.ui.screens.AcceptBookingScreen(bookingId = e.arguments?.getString("id").orEmpty(), onBack = { navController.popBackStack() }, onOpenJob = { id -> navController.navigate("autoKeyJob/$id") }, onOpenRequests = { navController.navigate("bookingRequests") }) }
                composable("search") { au.mainspring.nativeapp.ui.screens.SearchScreen(onBack = { navController.popBackStack() }, onOpenRoute = { navController.navigate(it) }) }
                composable("sendBookingRequest") { au.mainspring.nativeapp.ui.screens.SendBookingRequestScreen(onBack = { navController.popBackStack() }) }
                composable("financeReport") { au.mainspring.nativeapp.ui.screens.MobileFinanceReportScreen(onBack = { navController.popBackStack() }) }
                composable("database") { au.mainspring.nativeapp.ui.screens.DatabaseScreen(onBack = { navController.popBackStack() }) }
                composable("catalogue") { au.mainspring.nativeapp.ui.screens.CatalogueScreen(onBack = { navController.popBackStack() }) }
                composable("shoeServices") { au.mainspring.nativeapp.ui.screens.ShoeServicesScreen(onBack = { navController.popBackStack() }) }
                composable("accounts") { au.mainspring.nativeapp.ui.screens.AccountsScreen(onBack = { navController.popBackStack() }, onSignOut = onLogout) }
                composable("customerOrders") { au.mainspring.nativeapp.ui.screens.CustomerOrdersScreen(onBack = { navController.popBackStack() }) }
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
                        onDeleted = { navController.popBackStack() },
                        onDuplicated = { navController.navigate("shoeJob/$it") },
                        onEditCustomer = { navController.navigate("editCustomer/$it") },
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
                        onOpenJob = { navController.navigate("autoKeyJob/$it") },
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
