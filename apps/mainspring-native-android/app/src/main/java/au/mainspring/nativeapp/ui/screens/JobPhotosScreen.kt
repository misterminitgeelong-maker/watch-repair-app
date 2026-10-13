package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import au.mainspring.nativeapp.ui.PrimaryAction as Button
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.JobPhotosViewModel
import au.mainspring.nativeapp.ui.PhotoThumbnail
import au.mainspring.nativeapp.ui.RefreshOnResume
import au.mainspring.nativeapp.ui.formatShopDate
import kotlinx.coroutines.launch
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobPhotosScreen(resource: String, id: String, onBack: () -> Unit,
    vm: JobPhotosViewModel = viewModel(key = "$resource/$id", factory = JobPhotosViewModel.factory(resource, id)), embedded: Boolean = false) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var localError by remember { mutableStateOf<String?>(null) }
    var confirmUpload by remember { mutableStateOf(false) }
    val editable = !state.busy && !state.uncertain
    RefreshOnResume(vm::refresh)
    BackHandler { if(!state.busy) onBack() }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if(uri != null) {
            try { context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            catch(_: SecurityException) { localError = "Reselect this file if its provider stops allowing access after closing the app." }
            vm.select(uri.toString())
        }
    }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { success -> vm.cameraFinished(success) }
    Scaffold(contentWindowInsets = if(embedded) WindowInsets(0,0,0,0) else ScaffoldDefaults.contentWindowInsets, topBar = { if(!embedded) au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Job photos and files") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onClick = onBack, enabled = !state.busy) }) }) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize().imePadding(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                if(state.busy || state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }; localError?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }; state.info?.let { Text(it) }
                androidx.compose.material3.TextButton(onClick = vm::refresh, enabled = !state.busy && !state.loading) { Text("Refresh") }
                if(state.uncertain) {
                    Text("Refresh to look for the previously uploaded photo. Review the files before repeating the upload.")
                    OutlinedButton(onClick = vm::checkedFiles, enabled = state.historyChecked && !state.busy && !state.loading) { Text("I checked that this photo is missing") }
                }
                if(state.draft.cameraUri.isNotBlank()) {
                    Text("An unfinished camera capture is retained on this device.")
                    OutlinedButton(onClick = { vm.cameraFinished(false) }, enabled = editable) { Text("Discard unfinished capture") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        try {
                            val directory = File(context.filesDir, "intake-photos").apply { mkdirs() }
                            val file = File.createTempFile("job-photo-", ".jpg", directory)
                            val uri = FileProvider.getUriForFile(context, "${context.packageName}.intake", file)
                            vm.cameraStarted(uri.toString()); camera.launch(uri)
                        } catch(e: Exception) { localError = e.message ?: "Could not open the camera." }
                    }, enabled = editable) { Text("Camera") }
                    OutlinedButton(onClick = { picker.launch(arrayOf("image/jpeg", "image/png", "image/webp")) }, enabled = editable) { Text("Choose photo") }
                }
                if(state.draft.uri.isNotBlank()) {
                    PhotoThumbnail(state.draft.uri, "Selected job photo")
                    au.mainspring.nativeapp.ui.AtelierTextField(state.draft.label, vm::label, label = { Text("Photo label") }, enabled = editable, modifier = Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(onClick = { vm.select("") }, enabled = editable) { Text("Remove selected photo") }
                        Button(onClick = { confirmUpload = true }, enabled = editable && !state.loading) { Text("Upload photo") }
                    }
                    Text("The selected photo stays in your account's draft until uploaded or removed.")
                }
                Text("Saved job files", style = MaterialTheme.typography.titleMedium)
                Text("${state.files.size} saved files loaded")
                if(!state.loading && state.files.isEmpty()) Text("No files found on this job.")
            }
            items(state.files, key = { it.id }) { file ->
                au.mainspring.nativeapp.ui.FlatPanel { Column {
                    Text(file.label?.takeIf { it.isNotBlank() } ?: file.fileName ?: "Job file", style = MaterialTheme.typography.titleMedium)
                    Text(formatShopDate(file.createdAt), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    TextButton(onClick = { scope.launch {
                        try { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(vm.downloadLink(file)))) }
                        catch(e: Exception) { localError = "Could not open this file. ${e.message.orEmpty()}" }
                    } }) { Text("Open file") }
                } }
            }
            if(state.hasMore) item { OutlinedButton(onClick = vm::loadMore, enabled = !state.busy && !state.loading) { Text("Load older files") } }
        }
    }
    if(confirmUpload) AlertDialog(onDismissRequest = { confirmUpload = false }, title = { Text("Upload this photo?") },
        text = { Text("Save the selected photo on this job with the label '${state.draft.label}'.") },
        confirmButton = { TextButton(onClick = { confirmUpload = false; vm.upload(context.applicationContext) }) { Text("Confirm upload") } },
        dismissButton = { TextButton(onClick = { confirmUpload = false }) { Text("Cancel") } })
}
