package au.mainspring.nativeapp

import android.graphics.Bitmap
import androidx.core.content.FileProvider
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.ui.MainspringTheme
import au.mainspring.nativeapp.ui.screens.JobPhotosScreen
import okhttp3.mockwebserver.*
import org.junit.*
import java.io.File

class JobPhotosWorkflowTest {
    @get:Rule val compose = createComposeRule()
    private lateinit var server: MockWebServer
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private var uploads = 0
    private var loseResponse = false
    private var savedName = ""
    private var uploadPath = ""
    private var pages = false
    private fun attachment(id: String, filename: String) = """{"id":"$id","storage_key":"photos/$id.jpg","file_name":"$filename","label":"Diagnostic photo","created_at":"2026-10-07T00:00:00Z"}"""
    @Before fun setup() {
        TokenStore.init(context); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object: Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if(request.method == "POST") {
                    uploads++; uploadPath = request.path.orEmpty()
                    val multipart = request.body.readUtf8()
                    savedName = Regex("filename=\"([^\"]+)\"").find(multipart)!!.groupValues[1]
                    Assert.assertTrue(multipart.contains("Content-Type: image/jpeg"))
                    if(loseResponse) return MockResponse().setResponseCode(503)
                    return MockResponse().setBody(attachment("photo-1", savedName)).setHeader("Content-Type", "application/json")
                }
                val body = if(pages) {
                    if(request.path.orEmpty().contains("offset=50")) "[${attachment("older", "old.jpg")}]"
                    else (1..50).joinToString(",", "[", "]") { attachment("photo-$it", "photo-$it.jpg") }
                } else if(savedName.isBlank()) "[]" else "[${attachment("photo-1", savedName)}]"
                return MockResponse().setBody(body).setHeader("Content-Type", "application/json")
            }
        }; server.start(); TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("photos", "operator")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }
    private fun photo(valid: Boolean = true): Pair<File, String> {
        val file = File.createTempFile("evidence-", ".jpg", File(context.filesDir, "intake-photos").apply { mkdirs() })
        if(valid) {
            val bitmap = Bitmap.createBitmap(40,20,Bitmap.Config.ARGB_8888)
            file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 90, it) }; bitmap.recycle()
        } else file.writeText("Not an image")
        return file to FileProvider.getUriForFile(context, "${context.packageName}.intake", file).toString()
    }
    private fun vm(resource: String = "auto-key-jobs") = JobPhotosViewModel(resource, "job-1").also { model -> compose.waitUntil(10_000) { !model.state.value.loading } }

    @Test fun nativeUploadConfirmsJobScopeAndCleansAcknowledgedCameraFile() {
        val model = vm(); val (file, uri) = photo(); model.select(uri); model.label("Diagnostic photo")
        compose.setContent { MainspringTheme { JobPhotosScreen("auto-key-jobs", "job-1", {}, model) } }
        compose.onNodeWithText("Upload photo").performScrollTo().performClick(); Assert.assertEquals(0,uploads)
        compose.onNodeWithText("Confirm upload").performClick()
        compose.waitUntil(10_000) { !model.state.value.busy && model.state.value.files.isNotEmpty() }
        Assert.assertEquals(1,uploads); Assert.assertTrue(uploadPath.contains("auto_key_job_id=job-1")); Assert.assertFalse(uploadPath.contains("repair_job_id="))
        Assert.assertEquals("", model.state.value.draft.uri); Assert.assertFalse(file.exists())
        saveNativeQaImage(compose.onRoot(), "mobile-job-photo-complete.png")
    }
    @Test fun lostUploadResponseRecoversSameFilenameWithoutAnotherPost() {
        loseResponse = true
        val model = vm(); val (_, uri) = photo(); model.select(uri); model.upload(context)
        compose.waitUntil(10_000) { !model.state.value.busy }; Assert.assertTrue(model.state.value.uncertain)
        model.upload(context); Assert.assertEquals(1, uploads)
        val restored = vm(); Assert.assertFalse(restored.state.value.uncertain); Assert.assertEquals("",restored.state.value.draft.uri)
        Assert.assertTrue(restored.state.value.info.orEmpty().contains("Recovered")); Assert.assertEquals(1,uploads)
    }
    @Test fun unreadablePhotoIsRejectedBeforeAnyNetworkUpload() {
        val model = vm("shoe-repair-jobs"); val (_, uri) = photo(false); model.select(uri); model.upload(context)
        compose.waitUntil(10_000) { !model.state.value.busy }
        Assert.assertEquals(0,uploads); Assert.assertFalse(model.state.value.uncertain); Assert.assertNotNull(model.state.value.error)
    }
    @Test fun pendingCameraCaptureSurvivesRecreationAndCanBeDiscardedSafely() {
        val model = vm("repair-jobs"); val (file, uri) = photo(); model.cameraStarted(uri)
        val restored = vm("repair-jobs"); Assert.assertEquals(uri,restored.state.value.draft.cameraUri)
        Assert.assertTrue(file.exists()); restored.cameraFinished(false); Assert.assertFalse(file.exists())
        Assert.assertEquals(0,uploads)
    }
    @Test fun olderFilesUseServerOffsetAndRemainOnSameJob() {
        pages = true; val model = vm(); Assert.assertTrue(model.state.value.hasMore)
        model.loadMore(); compose.waitUntil(10_000) { !model.state.value.loading }
        Assert.assertEquals(51, model.state.value.files.size); Assert.assertFalse(model.state.value.hasMore)
        Assert.assertEquals("older",model.state.value.files.last().id); Assert.assertEquals(0,uploads)
    }
}
