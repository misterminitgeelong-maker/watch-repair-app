package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
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
@Composable fun RouteScreen(onBack: () -> Unit,onJob: (String) -> Unit,model: TodayViewModel = viewModel(key="route-today")) {
    val state by model.state.collectAsStateWithLifecycle()
    val context=LocalContext.current
    var error by remember {mutableStateOf<String?>(null)}
    val stops=state.jobs.filter { !it.jobAddress.isNullOrBlank() }.sortedWith(compareBy({it.visitOrder ?: Int.MAX_VALUE},{bookingInstant(it.scheduledAt)}))
    RefreshOnResume(model::refresh)
    fun navigate(address: String) {
        try { context.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse("https://www.google.com/maps/dir/").buildUpon().appendQueryParameter("api","1").appendQueryParameter("destination",address).appendQueryParameter("travelmode","driving").build())) }
        catch(_: android.content.ActivityNotFoundException) {error="No maps app or browser is available."}
    }
    Scaffold(topBar={TopAppBar(title={Text("Today's route",style=MaterialTheme.typography.titleLarge)},navigationIcon={au.mainspring.nativeapp.ui.BackButton(onBack)},actions={TextButton(model::refresh,enabled=!state.loading) { Text("Refresh") }})}) {padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            if(BuildConfig.MAPS_CONFIGURED) NativeStopMap(stops.map {it.jobAddress.orEmpty()},Modifier.fillMaxWidth().height(240.dp))
            else Surface(Modifier.fillMaxWidth().height(150.dp),color=MaterialTheme.colorScheme.secondaryContainer) {
                Column(Modifier.padding(24.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                    FieldIcon("Map");Text("Your route, stop by stop",style=MaterialTheme.typography.headlineSmall)
                    Text("The in-app map is unavailable in this build. Navigate to each stop using your maps app.",style=MaterialTheme.typography.bodySmall)
                }
            }
            LazyColumn(Modifier.weight(1f),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
                item {SectionLabel("Where to go · ${stops.size} stops");Text("Stops follow saved visit order, then booking time.",style=MaterialTheme.typography.bodySmall)}
                if(state.loading) item {LinearProgressIndicator(Modifier.fillMaxWidth())}
                (error ?: state.error)?.let {item {au.mainspring.nativeapp.ui.ErrorBanner(it)}}
                if(state.jobs.size>stops.size) item {Text("${state.jobs.size-stops.size} jobs have no address. Add an address in the job before navigating.",style=MaterialTheme.typography.bodySmall)}
                itemsIndexed(stops,key={_,job->job.id}) {index,job -> FlatPanel {
                    Row(horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                        Text("${index+1}",style=MaterialTheme.typography.titleLarge,color=MaterialTheme.colorScheme.primary)
                        Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(4.dp)) {
                            Text(job.title,style=MaterialTheme.typography.titleSmall)
                            Text(job.jobAddress.orEmpty(),style=MaterialTheme.typography.bodySmall)
                            job.scheduledAt?.let {Text(formatShopDate(it,TokenStore.calendarTimezone()),style=MaterialTheme.typography.labelSmall)}
                            StatusPill(job.status)
                        }
                    }
                    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                        OutlinedButton({onJob(job.id)},shape=MaterialTheme.shapes.small) {Text("Open job")}
                        Button({navigate(job.jobAddress.orEmpty())},shape=MaterialTheme.shapes.small) {Text("Navigate")}
                    }
                } }
                if(stops.isEmpty() && !state.loading) item {Text("No stops with an address today.")}
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
