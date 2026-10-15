package au.mainspring.nativeapp.niimbot

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull

/** Byte pipe to a printer. The BLE implementation lives in [NiimbotBleTransport]; tests use a fake. */
interface NiimbotTransport {
    /** True when the device has a notify characteristic (replies can be awaited). */
    val canNotify: Boolean
    /** True when writes are acknowledged (large batched writes are safe); false = write-without-response, pace per packet. */
    val writesAcknowledged: Boolean
    /** Called with each raw notification payload. */
    fun setListener(listener: ((ByteArray) -> Unit)?)
    /** Write bytes, splitting to the MTU as needed. Throws on failure. */
    suspend fun write(bytes: ByteArray)
}

/**
 * Print-job lifecycle over a [NiimbotTransport], ported from NiimbotPrinter in niimbot.ts. [pause] is injectable
 * so unit tests run without real delays.
 */
class NiimbotSession(
    private val transport: NiimbotTransport,
    private val pause: suspend (Long) -> Unit = { delay(it) },
) {
    private class Waiter(val respCmd: Int, val result: CompletableDeferred<NiimbotPacket>)

    private val reassembler = PacketReassembler()
    private val waiters = ArrayList<Waiter>()

    init {
        transport.setListener { bytes ->
            val packets = synchronized(reassembler) { reassembler.feed(bytes) }
            for (p in packets) {
                val w = synchronized(waiters) { waiters.indexOfFirst { it.respCmd == p.cmd }.takeIf { it >= 0 }?.let { waiters.removeAt(it) } }
                w?.result?.complete(p)
            }
        }
    }

    fun close() = transport.setListener(null)

    /** Send a command and wait for its reply (reply cmd = cmd + respOffset). Null on timeout or no notify channel. */
    private suspend fun transceive(packet: ByteArray, cmd: Int, respOffset: Int = 1, timeoutMs: Long = 1500): NiimbotPacket? {
        if (!transport.canNotify) { transport.write(packet); return null }
        val waiter = Waiter(cmd + respOffset, CompletableDeferred())
        synchronized(waiters) { waiters.add(waiter) }
        try {
            transport.write(packet)
            return withTimeoutOrNull(timeoutMs) { waiter.result.await() }
        } finally {
            synchronized(waiters) { waiters.remove(waiter) }
        }
    }

    /** Heartbeat then read the loaded label size; null size means "use the default roll". */
    suspend fun handshake(): LabelDots? {
        transport.write(NiimbotProtocol.heartbeat())
        return try {
            NiimbotProtocol.labelDotsFromRfid(transceive(NiimbotProtocol.getRfid(), NiimbotProtocol.CMD_GET_RFID, 1, 2000))
        } catch (e: java.io.IOException) {
            null
        }
    }

    /**
     * Print all pages as ONE job (separate jobs per label make the printer drop labels). Throws on write failure.
     */
    suspend fun print(pages: List<RasterPage>, quantityPerPage: Int = 1) {
        if (pages.isEmpty()) return
        val totalPages = pages.size * quantityPerPage
        transport.write(NiimbotProtocol.setLabelType()); pause(50)
        transport.write(NiimbotProtocol.setDensity(3)); pause(50)
        transport.write(NiimbotProtocol.startPrint(totalPages)); pause(400)
        for (page in pages) {
            transport.write(NiimbotProtocol.startPage()); pause(50)
            transport.write(NiimbotProtocol.setDimension(page.height, page.width, quantityPerPage)); pause(50)
            streamRows(page.rowPackets); pause(150)
            transport.write(NiimbotProtocol.endPage()); pause(100)
        }
        waitForPrintComplete(totalPages)
        // END_PRINT: retry until the printer acks the job end (non-zero first data byte).
        for (attempt in 0 until 10) {
            val reply = transceive(NiimbotProtocol.endPrint(), NiimbotProtocol.CMD_END_PRINT, 1, 800) ?: break
            if (reply.data.isNotEmpty() && reply.data[0].toInt() != 0) break
            pause(200)
        }
    }

    private suspend fun streamRows(rowPackets: List<ByteArray>) {
        if (transport.writesAcknowledged) {
            for (chunk in NiimbotProtocol.batchPackets(rowPackets)) { transport.write(chunk); pause(15) }
        } else {
            for ((i, p) in rowPackets.withIndex()) { transport.write(p); if (i % 4 == 3) pause(20) }
        }
    }

    private suspend fun waitForPrintComplete(totalPages: Int, maxPolls: Int = 100) {
        if (!transport.canNotify) { pause(1500L + 1200L * totalPages); return }
        var misses = 0
        repeat(maxPolls) {
            val reply = transceive(NiimbotProtocol.getPrintStatus(), NiimbotProtocol.CMD_GET_PRINT_STATUS, 16, 1000)
            if (reply != null && reply.data.size >= 4) {
                misses = 0
                if (NiimbotProtocol.printComplete(reply, totalPages)) return
            } else if (++misses >= 3) {
                pause(1500L + 1200L * totalPages) // firmware does not answer status queries
                return
            }
            pause(300)
        }
    }
}
