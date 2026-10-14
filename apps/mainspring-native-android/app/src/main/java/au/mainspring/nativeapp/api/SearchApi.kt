package au.mainspring.nativeapp.api

import retrofit2.http.GET
import retrofit2.http.Query

/** One result of GET /v1/search. kind: repair_job | shoe_repair_job | auto_key_job | customer | quote | invoice. */
data class SearchHit(
    val kind: String = "",
    val id: String = "",
    val title: String? = null,
    val subtitle: String? = null,
    val status: String? = null,
    val href: String? = null,
)

data class SearchResponse(val hits: List<SearchHit>? = null)

/** Global search. Obtain via ApiClient.service(SearchApi::class.java). */
interface SearchApi {
    @GET("v1/search") suspend fun search(@Query("q") q: String, @Query("limit") limit: Int = 20): SearchResponse
}
