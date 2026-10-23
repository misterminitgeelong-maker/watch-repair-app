package au.mainspring.nativeapp

import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.*
import org.junit.*
import java.util.concurrent.ConcurrentLinkedQueue

/** Server calls behind the watch jobs list and job detail extras: full CSV export, filters and "set quote from movement". */
class WatchJobExtrasApiTest {
    private lateinit var server: MockWebServer
    private val requests = ConcurrentLinkedQueue<String>()

    @Before fun setup() {
        TokenStore.init(InstrumentationRegistry.getInstrumentation().targetContext); TokenStore.clear()
        server = MockWebServer(); server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty()
                requests.add("${request.method} $path ${request.body.readUtf8()}")
                val json = { body: String -> MockResponse().setHeader("Content-Type", "application/json").setBody(body) }
                return when {
                    path.startsWith("/v1/repair-jobs/export.csv") -> MockResponse().setHeader("Content-Type", "text/csv").setBody("Job,Title\r\n1,Service\r\n")
                    path.startsWith("/v1/watch-catalogue/movements/eta-2824/quote") -> json("""{"quote_cents":18000,"cost_cents":9000}""")
                    path.startsWith("/v1/repair-jobs?") -> json("[]")
                    else -> json("{}")
                }
            }
        }; server.start()
        TokenStore.saveApiBaseUrl(server.url("/").toString()); TokenStore.setDraftScope("tenant-1", "user-1"); TokenStore.setSessionRole("owner")
    }
    @After fun cleanup() { TokenStore.clear(); server.shutdown() }

    @Test fun jobsCsvComesFromTheServerExport() = runBlocking {
        val vm = JobsViewModel()
        val bytes = vm.downloadCsv()
        Assert.assertEquals("Job,Title\r\n1,Service\r\n", String(bytes))
        Assert.assertTrue(requests.any { it.startsWith("GET /v1/repair-jobs/export.csv") })
    }

    @Test fun costOutlierFilterAndSortGoToTheServer() {
        val vm = JobsViewModel()
        vm.setCostOutliersOnly(true)
        vm.setSort(JobSort.JOB_NUMBER)
        vm.setSortDescending(false)
        val end = System.currentTimeMillis() + 10_000
        while (requests.none { it.contains("cost_outlier=true") && it.contains("sort_by=job_number") && it.contains("sort_dir=asc") } && System.currentTimeMillis() < end) Thread.sleep(50)
        Assert.assertTrue(requests.any { it.contains("cost_outlier=true") && it.contains("sort_by=job_number") && it.contains("sort_dir=asc") })
    }

    @Test fun movementQuoteIsFetchedByKey() = runBlocking {
        val quote = au.mainspring.nativeapp.api.ApiClient.service(au.mainspring.nativeapp.api.CatalogueApi::class.java).watchMovementQuote("eta-2824")
        Assert.assertEquals(18000, quote.quoteCents)
        Assert.assertEquals(9000, quote.costCents)
    }
}
