package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.screens.LinkAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import android.content.Intent
import android.location.Geocoder
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.ui.*
import com.google.android.gms.maps.*
import com.google.android.gms.maps.model.*
import kotlinx.coroutines.*
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun RouteScreen(onBack: () -> Unit,onJob: (String) -> Unit,model: TodayViewModel = viewModel(key="route-today"),dayModel: RouteDayViewModel = viewModel(key="route-day"),orderModel: RouteOrderViewModel = viewModel(),geocode: (suspend (String) -> Pair<Double,Double>?)? = null) {
    val state by model.state.collectAsStateWithLifecycle()
    val context=LocalContext.current
    var error by remember {mutableStateOf<String?>(null)}
    val order by orderModel.state.collectAsStateWithLifecycle()
    val scope=rememberCoroutineScope()
    var locating by remember {mutableStateOf(false)}
    val deviceGeocode: suspend (String) -> Pair<Double,Double>? = geocode ?: {address -> withContext(Dispatchers.IO) {
        if(!Geocoder.isPresent()) null else try {
            @Suppress("DEPRECATION") Geocoder(context,Locale.getDefault()).getFromLocationName(address,1)?.firstOrNull()?.let {it.latitude to it.longitude}
        } catch(_: java.io.IOException) {null}
    }}
    val dayState by dayModel.state.collectAsStateWithLifecycle()
    var dayOffset by rememberSaveable {mutableIntStateOf(0)}
    var techFilter by rememberSaveable {mutableStateOf<String?>(null)}
    var statusFilter by rememberSaveable {mutableStateOf<String?>(null)}
    val isToday=dayOffset==0
    val sourceJobs=if(isToday) state.jobs else dayState.jobs
    val loading=if(isToday) state.loading else dayState.loading
    val loadError=if(isToday) state.error else dayState.error
    val refreshAll: () -> Unit={ if(isToday) model.refresh() else dayModel.refresh() }
    val statuses=sourceJobs.map {it.status}.distinct().sorted()
    val filtered=filterRouteJobs(sourceJobs.filter { !it.jobAddress.isNullOrBlank() },techFilter,statusFilter)
    val baseStops=filtered.sortedWith(compareBy({it.visitOrder ?: Int.MAX_VALUE},{bookingInstant(it.scheduledAt)}))
    var draft by remember {mutableStateOf<List<String>?>(null)}
    val stops=draft?.let {ids -> val byId=baseStops.associateBy {it.id};ids.mapNotNull {byId[it]}.let {listed -> listed+baseStops.filter {s -> listed.none {l -> l.id==s.id}}}} ?: baseStops
    val filtersActive=techFilter!=null || statusFilter!=null
    val canReorder=TokenStore.canWorkJobs() && !filtersActive && stops.size>=2
    LaunchedEffect(dayOffset,techFilter,statusFilter) {draft=null}
    LaunchedEffect(dayOffset) {if(dayOffset!=0) dayModel.setDay(java.time.LocalDate.now().plusDays(dayOffset.toLong()))}
    RefreshOnResume(refreshAll)
    LaunchedEffect(order.message,order.error) {if(order.changed>0) {draft=null;refreshAll()}}
    fun move(from: Int,to: Int) {draft=moveItem(stops.map {it.id},from,to)}
    fun navigate(address: String) {
        try { context.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse("https://www.google.com/maps/dir/").buildUpon().appendQueryParameter("api","1").appendQueryParameter("destination",address).appendQueryParameter("travelmode","driving").build())) }
        catch(_: android.content.ActivityNotFoundException) {error="No maps app or browser is available."}
    }
    Scaffold(topBar={au.mainspring.nativeapp.ui.AtelierTopAppBar(title={Text("Today's route")},navigationIcon={au.mainspring.nativeapp.ui.BackButton(onBack)},actions={TextButton(refreshAll,enabled=!loading) { Text("Refresh") }})}) {padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if(BuildConfig.MAPS_CONFIGURED) NativeStopMap(stops.map {it.jobAddress.orEmpty()},Modifier.fillMaxWidth().height(240.dp))
            else Surface(Modifier.fillMaxWidth().heightIn(min=150.dp),color=if(LocalCalibre.current) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.secondaryContainer) {
                Column(Modifier.padding(24.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                    FieldIcon("Map");Text("Your route, stop by stop",style=MaterialTheme.typography.headlineSmall)
                    Text("The in-app map is unavailable in this build. Navigate to each stop using your maps app.",style=MaterialTheme.typography.bodySmall)
                    if(LocalCalibre.current) MonoLabel("Illustrative area diagram")
                }
            }
            PullToRefreshBox(isRefreshing=loading,onRefresh=refreshAll,modifier=Modifier.weight(1f)) {
            LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
                item {if(LocalCalibre.current) {MonoLabel("Where to go");Text("${stops.size} stops",style=MaterialTheme.typography.headlineMedium)} else SectionLabel("Where to go · ${stops.size} stops");Text("Stops follow saved visit order, then booking time.",style=MaterialTheme.typography.bodySmall)}
                item {
                    Column(Modifier.testTag("route-filters"),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                        Row(Modifier.fillMaxWidth(),verticalAlignment=androidx.compose.ui.Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                            TextButton({dayOffset--},Modifier.heightIn(min=48.dp)) {Text("Previous day")}
                            Text(routeDayLabel(dayOffset),Modifier.weight(1f).semantics {heading()},style=MaterialTheme.typography.titleSmall)
                            TextButton({dayOffset++},Modifier.heightIn(min=48.dp)) {Text("Next day")}
                        }
                        if(!isToday) TextButton({dayOffset=0},Modifier.heightIn(min=48.dp)) {Text("Back to today")}
                        if(dayState.technicians.size>1) FilterRow(listOf<Pair<String?,String>>(null to "All technicians",ROUTE_UNASSIGNED to "Unassigned")+dayState.technicians.map {it.id to it.name},techFilter,{techFilter=it})
                        if(statuses.size>1 || statusFilter!=null) FilterRow(listOf<Pair<String?,String>>(null to "All statuses")+statuses.map {it to statusLabel(it)},statusFilter,{statusFilter=it})
                        if(filtersActive) Text("Filtered. Reordering is off while filters are on.",style=MaterialTheme.typography.bodySmall)
                    }
                }
                if(canReorder) item {
                    Column(verticalArrangement=Arrangement.spacedBy(4.dp)) {
                        Text("Drag the handle, or use Move up and Move down, then save the order.",style=MaterialTheme.typography.bodySmall)
                        if(draft!=null) Row(horizontalArrangement=Arrangement.spacedBy(16.dp)) {
                            Button({orderModel.saveOrder(stops)},enabled=!order.busy) {Text(if(order.busy) "Saving order…" else "Save stop order")}
                            OutlinedButton({draft=null},enabled=!order.busy) {Text("Discard changes")}
                        }
                    }
                }
                if(TokenStore.canWorkJobs() && stops.size>=2) item {
                    Column(verticalArrangement=Arrangement.spacedBy(6.dp)) {
                        Row(horizontalArrangement=Arrangement.spacedBy(16.dp)) {
                            OutlinedButton({
                                scope.launch {
                                    locating=true
                                    try {
                                        val byTime=stops.sortedBy {bookingInstant(it.scheduledAt) ?: java.time.Instant.MAX}
                                        val located=byTime.mapNotNull {job -> deviceGeocode(job.jobAddress.orEmpty())?.let {LocatedStop(job,it.first,it.second)}}
                                        orderModel.optimise(located)
                                    } finally {locating=false}
                                }
                            },enabled=!order.busy && !locating && draft==null) {Text(if(locating) "Locating stops…" else if(order.busy) "Saving order…" else "Optimise order")}
                            if(stops.any {it.visitOrder!=null}) OutlinedButton({orderModel.clear(stops)},enabled=!order.busy && !locating) {Text("Clear saved order")}
                        }
                        order.message?.let {Text(it,style=MaterialTheme.typography.bodySmall)}
                        order.error?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)}
                    }
                }
                if(loading) item {LinearProgressIndicator(Modifier.fillMaxWidth())}
                (error ?: loadError)?.let {item {au.mainspring.nativeapp.ui.ErrorBanner(it)}}
                if(!filtersActive && sourceJobs.size>stops.size) item {Text("${sourceJobs.size-stops.size} jobs have no address. Add an address in the job before navigating.",style=MaterialTheme.typography.bodySmall)}
                itemsIndexed(stops,key={_,job->job.id}) {index,job -> if(LocalCalibre.current) {
                    Column(Modifier.fillMaxWidth()) {
                        HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
                        Row(Modifier.padding(vertical=12.dp),horizontalArrangement=Arrangement.spacedBy(14.dp)) {
                            Text("%02d".format(index+1),style=Calibre.label.copy(fontSize=13.sp),color=MaterialTheme.colorScheme.primary,modifier=Modifier.padding(top=3.dp))
                            Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                                Text(job.title,style=MaterialTheme.typography.titleMedium)
                                MonoLabel(job.jobAddress.orEmpty())
                                job.scheduledAt?.let {MonoLabel(formatShopDate(it,TokenStore.calendarTimezone()))}
                                StatusPill(job.status)
                                if(canReorder) ReorderControls(index,stops.size,::move)
                                Row(horizontalArrangement=Arrangement.spacedBy(20.dp)) {
                                    OutlinedButton({onJob(job.id)}) {Text("Open job")}
                                    OutlinedButton({navigate(job.jobAddress.orEmpty())}) {Text("Navigate")}
                                }
                            }
                        }
                    }
                } else FlatPanel {
                    Row(horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                        Text("${index+1}",style=MaterialTheme.typography.titleLarge,color=MaterialTheme.colorScheme.primary)
                        Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                            Text(job.title,style=MaterialTheme.typography.titleSmall)
                            Text(job.jobAddress.orEmpty(),style=MaterialTheme.typography.bodySmall)
                            job.scheduledAt?.let {Text(formatShopDate(it,TokenStore.calendarTimezone()),style=MaterialTheme.typography.labelSmall)}
                            StatusPill(job.status)
                        }
                    }
                    if(canReorder) ReorderControls(index,stops.size,::move)
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                        OutlinedButton({onJob(job.id)},shape=MaterialTheme.shapes.small) {Text("Open job")}
                        Button({navigate(job.jobAddress.orEmpty())},shape=MaterialTheme.shapes.small) {Text("Navigate")}
                    }
                } }
                if(stops.isEmpty() && !loading) item {Text(if(filtersActive) "No stops match these filters." else "No stops with an address ${routeDayLabel(dayOffset).lowercase()}.")}
            }
            }
            if(stops.isNotEmpty()) Button({navigate(stops.first().jobAddress.orEmpty())},modifier=Modifier.fillMaxWidth().padding(16.dp),shape=MaterialTheme.shapes.small) {Text("Start navigation to stop 1")}
        }
    }
}

@Composable private fun NativeStopMap(addresses: List<String>,modifier: Modifier) {
    val context=LocalContext.current
    val lifecycle=LocalLifecycleOwner.current.lifecycle
    val view=remember { MapView(context).apply {onCreate(null)} }
    var mapLoaded by remember {mutableStateOf(false)}
    var mapFailed by remember {mutableStateOf(false)}
    var map by remember {mutableStateOf<GoogleMap?>(null)}
    var points by remember {mutableStateOf<List<Pair<String,LatLng>>>(emptyList())}
    var resolving by remember {mutableStateOf(false)}
    DisposableEffect(view,lifecycle) {
        val observer=LifecycleEventObserver {_,event -> when(event) {
            Lifecycle.Event.ON_START -> view.onStart(); Lifecycle.Event.ON_RESUME -> view.onResume()
            Lifecycle.Event.ON_PAUSE -> view.onPause(); Lifecycle.Event.ON_STOP -> view.onStop(); else -> Unit
        } }
        lifecycle.addObserver(observer)
        onDispose {lifecycle.removeObserver(observer);view.onPause();view.onStop();view.onDestroy()}
    }
    LaunchedEffect(view) {delay(15_000);if(!mapLoaded) mapFailed=true}
    LaunchedEffect(addresses) {
        points=emptyList();resolving=true
        try {
            if(Geocoder.isPresent()) points=withContext(Dispatchers.IO) {
                val geocoder=Geocoder(context,Locale.getDefault())
                addresses.distinct().take(50).mapNotNull {address ->
                    ensureActive()
                    try {
                        @Suppress("DEPRECATION") val result=geocoder.getFromLocationName(address,1)?.firstOrNull()
                        result?.let { address to LatLng(it.latitude,it.longitude) }
                    } catch(_: java.io.IOException) {null}
                }
            }
        } finally {resolving=false}
    }
    LaunchedEffect(map,points,addresses) {
        map?.let { ready ->
            ready.clear()
            points.forEach { (address,position)->
                val order=addresses.mapIndexedNotNull {index,value->(index+1).takeIf {value==address}}.joinToString(", ")
                ready.addMarker(MarkerOptions().position(position).title("$order. $address"))
            }
            if(points.isNotEmpty()) view.post {
                if(points.size==1) ready.moveCamera(CameraUpdateFactory.newLatLngZoom(points.first().second,13f))
                else if(view.width>0 && view.height>0) ready.moveCamera(CameraUpdateFactory.newLatLngBounds(LatLngBounds.builder().also {b->points.forEach {b.include(it.second)}}.build(),40))
            }
        }
    }
    Box(modifier) {
        AndroidView(factory={view.also {it.getMapAsync {ready->map=ready;ready.setOnMapLoadedCallback {mapLoaded=true;mapFailed=false};ready.uiSettings.isMapToolbarEnabled=true}}},modifier=Modifier.fillMaxSize())
        if(mapFailed) Surface(Modifier.align(androidx.compose.ui.Alignment.Center).padding(16.dp),color=MaterialTheme.colorScheme.surface) {Text("Map could not load. Navigate to a stop using your maps app.",Modifier.padding(12.dp),style=MaterialTheme.typography.bodySmall)}
        Surface(Modifier.padding(8.dp),color=MaterialTheme.colorScheme.surface) {Text(if(resolving) "Locating stops…" else "${points.size} of ${addresses.distinct().size} addresses located",Modifier.padding(6.dp),style=MaterialTheme.typography.labelSmall)}
    }
}

internal fun routeDayLabel(offset: Int): String = when(offset) {
    0 -> "Today"; 1 -> "Tomorrow"; -1 -> "Yesterday"
    else -> java.time.LocalDate.now().plusDays(offset.toLong()).format(java.time.format.DateTimeFormatter.ofPattern("EEE d MMM",Locale.getDefault()))
}

/** Move up / Move down buttons (accessible) plus a vertical drag handle that swaps a stop each time it is dragged past one row. */
@Composable private fun ReorderControls(index: Int,count: Int,onMove: (Int,Int) -> Unit) {
    val rowPx=with(LocalDensity.current) {88.dp.toPx()}
    var drag by remember {mutableFloatStateOf(0f)}
    val position by rememberUpdatedState(index)
    val move by rememberUpdatedState(onMove)
    Row(verticalAlignment=androidx.compose.ui.Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(4.dp)) {
        Box(Modifier.size(48.dp).semantics {contentDescription="Drag to reorder stop ${index+1}"}.pointerInput(Unit) {
            detectVerticalDragGestures(onDragStart={drag=0f},onDragEnd={drag=0f},onDragCancel={drag=0f}) {change,amount ->
                change.consume();drag+=amount
                if(drag>rowPx && position<count-1) {move(position,position+1);drag=0f}
                else if(drag<-rowPx && position>0) {move(position,position-1);drag=0f}
            }
        },contentAlignment=androidx.compose.ui.Alignment.Center) {Text("≡",style=MaterialTheme.typography.titleLarge)}
        TextButton({onMove(index,index-1)},Modifier.heightIn(min=48.dp),enabled=index>0) {Text("Move up")}
        TextButton({onMove(index,index+1)},Modifier.heightIn(min=48.dp),enabled=index<count-1) {Text("Move down")}
    }
}
