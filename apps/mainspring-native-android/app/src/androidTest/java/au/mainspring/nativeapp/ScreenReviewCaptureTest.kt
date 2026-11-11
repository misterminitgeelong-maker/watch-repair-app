package au.mainspring.nativeapp

import android.app.Application
import android.graphics.Bitmap
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.ui.Modifier
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.LocalSaveableStateRegistry
import androidx.compose.runtime.saveable.SaveableStateRegistry
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.*
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.LocalViewModelStoreOwner
import androidx.savedstate.SavedStateRegistry
import androidx.savedstate.SavedStateRegistryController
import androidx.savedstate.SavedStateRegistryOwner
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.*
import au.mainspring.nativeapp.ui.*
import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import kotlinx.coroutines.runBlocking
import org.junit.Test
import org.junit.Rule
import org.junit.Assume
import java.io.File

private class ReviewOwner(app: Application): SavedStateRegistryOwner, ViewModelStoreOwner, HasDefaultViewModelProviderFactory {
    private val registry = SavedStateRegistryController.create(this)
    private val state = LifecycleRegistry(this)
    override val lifecycle: Lifecycle = state
    override val savedStateRegistry: SavedStateRegistry get() = registry.savedStateRegistry
    override val viewModelStore = ViewModelStore()
    override val defaultViewModelProviderFactory = SavedStateViewModelFactory(app, this)
    init { registry.performAttach(); registry.performRestore(null); state.currentState = Lifecycle.State.RESUMED }
    fun close() { state.currentState = Lifecycle.State.DESTROYED; viewModelStore.clear() }
}

/** Opt-in visual review only. Real composables and real disposable API; no production data. */
class ScreenReviewCaptureTest {
    @get:Rule val compose = createComposeRule()
    @Test fun captureScreensForUserReview(): Unit = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val args = InstrumentationRegistry.getArguments()
        val slug = args.getString("localTenantSlug")
        Assume.assumeTrue("Opt in with localhost screenshot fixture arguments", slug != null)
        require(slug!!.startsWith("native-qa-"))
        val email = requireNotNull(args.getString("localOwnerEmail")); require(email.endsWith("@native.example.test"))
        val context = instrumentation.targetContext
        TokenStore.init(context); TokenStore.clear(); TokenStore.saveApiBaseUrl("http://127.0.0.1:8716/")
        val token = ApiClient.api.login(LoginRequest(slug, email, "Native-local-test-only!"))
        TokenStore.saveTokens(token.accessToken, token.refreshToken)
        val session = ApiClient.api.session()
        TokenStore.setDraftScope(session.tenantId, session.user.id); TokenStore.setSessionRole(session.user.role)
        TokenStore.setIntegrationManagementAllowed(session.canManageIntegrations)
        TokenStore.setCalendarTimezone(session.calendarTimezone)
        TokenStore.setShopIdentity(session.currency, session.shopName, session.shopAbn, session.shopPhone, session.shopAddress)
        val idsJson = String(android.util.Base64.decode(requireNotNull(args.getString("reviewIdsBase64")), android.util.Base64.DEFAULT), Charsets.UTF_8)
        val ids = Gson().fromJson(idsJson, JsonObject::class.java).entrySet()
            .filter { it.value.isJsonPrimitive }.associate { it.key to it.value.asString }
        val data = ReviewData(session, ids)
        DesignPreferences.init(context); DesignPreferences.select(DEFAULT_APPEARANCE); DesignPreferences.fieldNavigation(false)
        val all = sharedReviewCases(data) + watchReviewCases(data) + mobileReviewCases(data) + communityReviewCases(data)
        require(all.map { it.id }.distinct().size == all.size)
        val selected = args.getString("reviewFilter")?.split(',')?.filter(String::isNotBlank).orEmpty()
        val cases = if(selected.isEmpty()) all else all.filter { c -> selected.any { c.id == it || c.group == it } }
        val outputName = args.getString("reviewOutputDir") ?: "screen-review-revised"
        require(outputName.matches(Regex("screen-review-[A-Za-z0-9_-]+"))) { "Use a separate screen-review-* folder; the original gallery must stay unchanged" }
        val output = File(context.getExternalFilesDir(null), outputName).apply { mkdirs() }
        val results = JsonArray()
        var active by mutableStateOf<ReviewCase?>(null)
        var owner by mutableStateOf<ReviewOwner?>(null)
        compose.setContent {
            active?.let { current -> key(current.id) {
                val saveables = remember { SaveableStateRegistry(null) { true } }
                CompositionLocalProvider(LocalViewModelStoreOwner provides owner!!, LocalLifecycleOwner provides owner!!,
                    androidx.compose.ui.platform.LocalSavedStateRegistryOwner provides owner!!,
                    LocalSaveableStateRegistry provides saveables) { MainspringTheme { ReviewRouteFrame(current, data) } }
            } }
        }
        for(case in cases) {
            val started = System.currentTimeMillis()
            var error: String? = null
            try {
                compose.runOnIdle { active = null }
                compose.waitForIdle()
                compose.runOnIdle {
                    owner?.close()
                    TokenStore.bindDrafts().apply { clearIntakeDraft(); clearShoeDraft(); clearMobileDraft() }
                    owner = ReviewOwner(context.applicationContext as Application)
                    active = case
                }
                compose.waitForIdle()
                Thread.sleep(900)
                case.prepare(compose)
                compose.waitForIdle()
                Thread.sleep(650)
                instrumentation.waitForIdleSync()
            } catch(e: Throwable) { error = "${e.javaClass.simpleName}: ${e.message}".take(1200) }
            try {
                val image = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
                File(output, "${case.id}.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
                image.recycle()
                File(output, "${case.id}.txt").writeText(runCatching { compose.onRoot(useUnmergedTree = true).printToString() }.getOrDefault("Semantics unavailable"))
            } catch(e: Throwable) { error = (error.orEmpty() + "; screenshot: " + e.message).take(1200) }
            results.add(JsonObject().apply {
                addProperty("id",case.id); addProperty("title",case.title); addProperty("group",case.group)
                addProperty("file","${case.id}.png"); addProperty("note",case.note)
                addProperty("status",if(error == null) "captured" else "needs-check"); addProperty("error",error)
                addProperty("elapsed_ms",System.currentTimeMillis() - started)
            })
            File(output, "manifest${if(selected.isEmpty()) "" else "-patch"}.json").writeText(Gson().toJson(results))
            println("SCREEN_REVIEW ${case.id}: ${error ?: "captured"}")
        }
        compose.runOnIdle { active = null }
        compose.waitForIdle(); compose.runOnIdle { owner?.close() }
        Unit
    }
}

/** Same production header/tab components and insets as MainspringAppShell for root routes. */
@Composable private fun ReviewRouteFrame(case: ReviewCase, data: ReviewData) {
    val id = case.id
    val route = when {
        id == "shared-jobs" -> "jobs"
        id == "shared-intake" -> "new_intake"
        id.startsWith("shared-tools") -> id.removePrefix("shared-")
        id == "shared-inbox" -> "inbox"
        id == "shared-leads" -> "leads"
        id == "shared-reports" -> "reports"
        id == "shared-inventory" -> "stock"
        id == "shared-counter-sale" -> "counterSale"
        id.startsWith("watch-directory") || id == "watch-board" || id == "watch-filters" -> "watch_jobs"
        id.startsWith("watch-customers") -> "customers"
        id in setOf("watch-quotes", "watch-quotes-filters", "watch-quote-job-picker") -> "quotes"
        id == "watch-invoices" -> "invoices"
        id in setOf("mobile-kanban", "mobile-directory", "mobile-list", "mobile-planner") || id.startsWith("mobile-filters") -> "auto_jobs"
        id.startsWith("mobile-today") || id == "mobile-run-sheet" -> "mobileToday"
        id == "mobile-dispatch" -> "dispatch"
        id == "mobile-route" -> "route"
        id == "mobile-pool" -> "dispatchPool"
        id == "mobile-booking-home" -> "today"
        id == "community-shoe-directory" || id == "community-shoe-cards" || id == "community-shoe-board" || id == "community-shoe-catalogue-tab" || id == "community-shoe-combos" -> "shoe_jobs"
        else -> null
    }
    val frameFeatures = if(id == "mobile-booking-home") setOf("shop_mobile_booking") else data.session.enabledFeatures.toSet()
    val sites = data.session.sites
    val activeSite = sites.firstOrNull { it.tenantId == (data.session.activeSiteId ?: data.session.tenantId) }
    var switchOpen by remember { mutableStateOf(false) }
    if(route == null) case.content()
    else Scaffold(contentWindowInsets = WindowInsets(0,0,0,0), topBar = { AppHeader({}, shopName = activeSite?.name,
        onSwitchShop = if(sites.map { it.tenantId }.distinct().size > 1) ({ switchOpen = true }) else null) },
        bottomBar = { FloatingTabBar(navTabs(frameFeatures), { it == tabFor(route, frameFeatures) }, {}) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(WindowInsets.statusBars)) { case.content() }
    }
    if(switchOpen) {
        val auth: AuthViewModel = androidx.lifecycle.viewmodel.compose.viewModel(key = "review-frame-auth")
        AlertDialog(onDismissRequest = { switchOpen = false }, title = { Text("Switch shop") }, text = {
            Column(Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState())) {
                Text("Unsaved drafts remain tied to the shop and account that opened them.")
                sites.forEach { site -> TextButton({ switchOpen = false; auth.switchSite(site.tenantId) }, enabled = site.tenantId != (data.session.activeSiteId ?: data.session.tenantId)) { Text(site.name) } }
            }
        }, confirmButton = { TextButton({ switchOpen = false }) { Text("Cancel") } })
    }
}
