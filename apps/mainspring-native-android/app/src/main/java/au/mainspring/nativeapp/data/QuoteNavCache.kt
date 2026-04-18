package au.mainspring.nativeapp.data

import au.mainspring.nativeapp.api.QuoteRead
import java.util.concurrent.ConcurrentHashMap

/** Holds quote rows from list navigation so detail can show totals without a single-quote GET. */
object QuoteNavCache {
    private val map = ConcurrentHashMap<String, QuoteRead>()

    operator fun get(id: String): QuoteRead? = map[id]

    fun put(quote: QuoteRead) {
        map[quote.id] = quote
    }

    fun putAll(quotes: List<QuoteRead>) {
        quotes.forEach { put(it) }
    }
}
