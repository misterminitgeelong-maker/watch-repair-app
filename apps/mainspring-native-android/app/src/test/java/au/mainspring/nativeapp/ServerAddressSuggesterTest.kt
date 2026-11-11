package au.mainspring.nativeapp
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.runBlocking
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.*
import java.io.IOException

class ServerAddressSuggesterTest {
 private class FakePlaces: PlacesApi {
  var failure: Exception? = null; var rows = listOf(PlaceSuggestion("ChIJabcdefghij1", "14 Burke Rd, Malvern East VIC, Australia"), PlaceSuggestion("ChIJabcdefghij2", "14 Burke St, Perth WA, Australia"))
  var detailsFailure: Exception? = null
  val autocompleteSessions = mutableListOf<String>(); val detailsCalls = mutableListOf<Pair<String, String>>(); var autocompleteCalls = 0
  override suspend fun autocomplete(query: String, session: String): PlaceSuggestionList { autocompleteCalls++; autocompleteSessions.add(session); failure?.let { throw it }; return PlaceSuggestionList(rows) }
  override suspend fun details(placeId: String, session: String): PlaceDetails { detailsCalls.add(placeId to session); detailsFailure?.let { throw it }; return PlaceDetails("14 Burke Rd, Malvern East VIC 3145, Australia", "Malvern East", "VIC", "3145") }
 }
 private class FakeFallback: AddressSuggester { var calls = 0; override suspend fun suggest(query: String): List<String> { calls++; return listOf("Device result for $query") } }
 private var clock = 1_000L
 private fun suggester(api: FakePlaces, fallback: FakeFallback = FakeFallback()) = ServerAddressSuggester({ api }, fallback, { clock })
 private fun http(code: Int) = retrofit2.HttpException(retrofit2.Response.error<Any>(code, "".toResponseBody()))

 @Test fun returnsTheServersSuggestionsAndNotTheDeviceOnes() = runBlocking {
  val fallback = FakeFallback(); val result = suggester(FakePlaces(), fallback).suggest("14 Burke")
  Assert.assertEquals(listOf("14 Burke Rd, Malvern East VIC, Australia", "14 Burke St, Perth WA, Australia"), result); Assert.assertEquals(0, fallback.calls)
 }
 @Test fun pickingAnAddressResolvesItWithTheSameSessionThenStartsANewSession() = runBlocking {
  val api = FakePlaces(); val s = suggester(api)
  val picked = s.suggest("14 Burke").first()
  Assert.assertEquals("14 Burke Rd, Malvern East VIC 3145, Australia", s.resolve(picked))
  Assert.assertEquals("ChIJabcdefghij1", api.detailsCalls.single().first)
  Assert.assertEquals("typing and the pick share one billing session", api.autocompleteSessions.single(), api.detailsCalls.single().second)
  s.suggest("22 Smith"); Assert.assertNotEquals(api.autocompleteSessions[0], api.autocompleteSessions[1])
 }
 @Test fun anUnknownPickIsReturnedUnchangedWithoutAskingTheServer() = runBlocking {
  val api = FakePlaces(); Assert.assertEquals("Typed by hand", suggester(api).resolve("Typed by hand")); Assert.assertTrue(api.detailsCalls.isEmpty())
 }
 @Test fun aFailedDetailsCallKeepsThePickedText() = runBlocking {
  val api = FakePlaces().apply { detailsFailure = IOException("offline") }; val s = suggester(api)
  val picked = s.suggest("14 Burke").first(); Assert.assertEquals(picked, s.resolve(picked))
 }
 @Test fun anUnconfiguredServerFallsBackAndIsNotAskedAgainForTenMinutes() = runBlocking {
  val api = FakePlaces().apply { failure = http(503) }; val fallback = FakeFallback(); val s = suggester(api, fallback)
  Assert.assertEquals(listOf("Device result for 14 Burke"), s.suggest("14 Burke"))
  clock += 9 * 60_000L; s.suggest("14 Burke R"); Assert.assertEquals(1, api.autocompleteCalls); Assert.assertEquals(2, fallback.calls)
  clock += 2 * 60_000L; api.failure = null; Assert.assertEquals(2, s.suggest("14 Burke Rd").size); Assert.assertEquals(2, api.autocompleteCalls)
 }
 @Test fun aNetworkFailureFallsBackForHalfAMinute() = runBlocking {
  val api = FakePlaces().apply { failure = IOException("no route") }; val fallback = FakeFallback(); val s = suggester(api, fallback)
  s.suggest("14 Burke"); clock += 10_000L; s.suggest("14 Burke R"); Assert.assertEquals(1, api.autocompleteCalls)
  clock += 25_000L; api.failure = null; s.suggest("14 Burke Rd"); Assert.assertEquals(2, api.autocompleteCalls)
 }
 @Test fun noMatchesIsAnEmptyListNotAFallback() = runBlocking {
  val api = FakePlaces().apply { rows = emptyList() }; val fallback = FakeFallback()
  Assert.assertTrue(suggester(api, fallback).suggest("zzzzz nowhere").isEmpty()); Assert.assertEquals(0, fallback.calls)
 }
}
