package au.mainspring.nativeapp
import androidx.test.platform.app.InstrumentationRegistry
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.runBlocking
import okhttp3.*
import okhttp3.ResponseBody.Companion.toResponseBody
import okhttp3.mockwebserver.*
import okhttp3.mockwebserver.Dispatcher
import org.junit.*
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.io.IOException

class SessionIsolationTest {
 private lateinit var server: MockWebServer
 @Before fun setup() {
  TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext);TokenStore.clear()
  server=MockWebServer();server.start();TokenStore.saveApiBaseUrl(server.url("/").toString())
  TokenStore.saveTokens("old-access","old-refresh");TokenStore.setDraftScope("old-tenant","old-user")
 }
 @After fun cleanup() { TokenStore.clear();server.shutdown() }
 @Test fun oldServiceCannotRetryRequestsUnderNewAccount()=runBlocking {
  server.enqueue(MockResponse().setBody("[]").setHeader("Content-Type","application/json"))
  val old=ApiClient.api
  TokenStore.saveTokens("new-access","new-refresh");TokenStore.setDraftScope("new-tenant","new-user")
  try { old.listCustomers();Assert.fail("Old service used new credentials") }catch(_: SessionChangedException){}
  Assert.assertEquals(0,server.requestCount)
  ApiClient.api.listCustomers();Assert.assertEquals("Bearer new-access",server.takeRequest(5,TimeUnit.SECONDS)!!.getHeader("Authorization"))
 }
 @Test fun lateDraftCallbacksCannotWriteIntoAnotherAccount() {
  val old=TokenStore.bindDrafts();old.saveMessageDraft("checkout","original old draft")
  TokenStore.saveTokens("new-access","new-refresh");TokenStore.setDraftScope("new-tenant","new-user")
  old.saveMessageDraft("checkout","late old callback");old.setPendingOperation("payment",true)
  val fresh=TokenStore.bindDrafts();Assert.assertEquals("",fresh.loadMessageDraft("checkout"));Assert.assertFalse(fresh.pendingOperation("payment"))
  TokenStore.saveTokens("old-again","old-refresh-again");TokenStore.setDraftScope("old-tenant","old-user")
  Assert.assertEquals("original old draft",TokenStore.bindDrafts().loadMessageDraft("checkout"))
 }
 @Test fun staleComposerRefusesSubmissionWhenItsCheckpointCannotBeSaved() {
  val composer = MessageThreadViewModel("auto-key-jobs", "old-job")
  composer.setDraft("Earlier account's message")
  TokenStore.saveTokens("new-access", "new-refresh"); TokenStore.setDraftScope("new-tenant", "new-user")
  composer.send()
  Assert.assertFalse(composer.state.value.sending)
  Assert.assertTrue(composer.state.value.error.orEmpty().contains("checkpoint"))
  Assert.assertEquals(0, server.requestCount)
  Assert.assertEquals("", TokenStore.bindDrafts().loadMessageDraft("auto-key-jobs/old-job"))
 }
 @Test fun delayedRefreshCannotOverwriteNewSignIn() {
  val started=CountDownLatch(1);val release=CountDownLatch(1)
  server.dispatcher=object:Dispatcher() { override fun dispatch(request:RecordedRequest):MockResponse {
   started.countDown();release.await(10,TimeUnit.SECONDS)
   return MockResponse().setHeader("Content-Type","application/json").setBody("""{"access_token":"old-rotated","refresh_token":"old-refresh-rotated"}""")
  } }
  val refresh=Retrofit.Builder().baseUrl(server.url("/")).addConverterFactory(GsonConverterFactory.create()).build().create(RefreshApi::class.java)
  val request=Request.Builder().url(server.url("/v1/customers")).header("Authorization","Bearer old-access").tag(SessionGenerationTag::class.java,SessionGenerationTag(TokenStore.sessionGeneration())).build()
  val response=Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(401).message("Unauthorized").body("".toResponseBody()).build()
  val executor=Executors.newSingleThreadExecutor()
  try {
   val pending=executor.submit<Request?> { TokenAuthenticator(refresh).authenticate(null,response) }
   Assert.assertTrue(started.await(5,TimeUnit.SECONDS));TokenStore.saveTokens("new-access","new-refresh");release.countDown()
   Assert.assertNull(pending.get(10,TimeUnit.SECONDS));Assert.assertEquals("new-access",TokenStore.getAccessToken());Assert.assertEquals("new-refresh",TokenStore.getRefreshToken())
  }finally { release.countDown();executor.shutdownNow();response.close() }
 }
 @Test fun refreshRotationWithinOneSessionStillWorks()=runBlocking {
  server.dispatcher=object:Dispatcher() { override fun dispatch(request:RecordedRequest):MockResponse {
   if(request.path=="/v1/auth/refresh") return MockResponse().setHeader("Content-Type","application/json").setBody("""{"access_token":"rotated-access","refresh_token":"rotated-refresh"}""")
   if(request.getHeader("Authorization")=="Bearer old-access") return MockResponse().setResponseCode(401)
   return MockResponse().setHeader("Content-Type","application/json").setBody("[]")
  } }
  val generation=TokenStore.sessionGeneration();ApiClient.api.listCustomers()
  Assert.assertEquals(generation,TokenStore.sessionGeneration());Assert.assertEquals("rotated-access",TokenStore.getAccessToken());Assert.assertEquals(3,server.requestCount)
 }
 @Test fun transientRefreshFailureRetainsSession()=runBlocking {
  server.dispatcher=object:Dispatcher() { override fun dispatch(request:RecordedRequest)=MockResponse().setResponseCode(if(request.path=="/v1/auth/refresh")503 else 401) }
  val generation=TokenStore.sessionGeneration()
  try { ApiClient.api.listCustomers();Assert.fail("Unavailable refresh succeeded") }catch(_:IOException){}
  Assert.assertEquals("old-access",TokenStore.getAccessToken());Assert.assertEquals(generation,TokenStore.sessionGeneration())
 }
}
