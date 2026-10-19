package au.mainspring.nativeapp.data
import au.mainspring.nativeapp.TokenStore
import au.mainspring.nativeapp.api.QuoteRead
import java.util.concurrent.ConcurrentHashMap
/** Cached navigation metadata belongs to the sign-in that fetched it. */
object QuoteNavCache {
 private data class Entry(val quote: QuoteRead,val generation: Long)
 private val map = ConcurrentHashMap<String,Entry>()
 operator fun get(id: String): QuoteRead? = map[id]?.takeIf { it.generation == TokenStore.sessionGeneration() }?.quote
 fun put(quote: QuoteRead,generation: Long) { if(generation == TokenStore.sessionGeneration()) map[quote.id] = Entry(quote,generation) }
 fun putAll(quotes: List<QuoteRead>,generation: Long) { quotes.forEach { put(it,generation) } }
 fun clear() { map.clear() }
}
