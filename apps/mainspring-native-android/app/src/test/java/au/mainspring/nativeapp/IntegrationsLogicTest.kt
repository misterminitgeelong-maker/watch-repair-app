package au.mainspring.nativeapp
import org.junit.*

class IntegrationsLogicTest {
 @Test fun webhookEventsAreSplitTrimmedAndBlanksDropped() {
  Assert.assertEquals(listOf("quote_approved", "job_created"), parseWebhookEvents(" quote_approved , job_created ,, "))
  Assert.assertEquals(listOf("*"), parseWebhookEvents("*"))
  Assert.assertTrue(parseWebhookEvents(" , ").isEmpty())
 }
 @Test fun newWebhooksStartWithTheSameEventsAsTheWeb() {
  Assert.assertEquals(listOf("quote_approved", "job_created"), parseWebhookEvents(DEFAULT_WEBHOOK_EVENTS))
 }
 @Test fun apiKeyBodiesMatchTheServerContract() {
  val gson = com.google.gson.Gson()
  Assert.assertEquals("""{"name":"Reports"}""", gson.toJson(au.mainspring.nativeapp.api.ApiKeyCreateBody("Reports")))
  Assert.assertEquals("""{"url":"https://a.example.test","event_types":["*"]}""", gson.toJson(au.mainspring.nativeapp.api.WebhookCreateBody("https://a.example.test", listOf("*"))))
  val created = gson.fromJson("""{"id":"k","name":"n","key_prefix":"msk_1","api_key":"msk_1_SECRET"}""", au.mainspring.nativeapp.api.ApiKeyCreated::class.java)
  Assert.assertEquals("msk_1_SECRET", created.apiKey)
 }
}
