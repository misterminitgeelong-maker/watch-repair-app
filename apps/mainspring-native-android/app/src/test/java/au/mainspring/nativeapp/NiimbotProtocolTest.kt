package au.mainspring.nativeapp

import au.mainspring.nativeapp.niimbot.LabelDots
import au.mainspring.nativeapp.niimbot.NiimbotPacket
import au.mainspring.nativeapp.niimbot.NiimbotProtocol
import au.mainspring.nativeapp.niimbot.NiimbotSession
import au.mainspring.nativeapp.niimbot.NiimbotTransport
import au.mainspring.nativeapp.niimbot.NiimbotUiState
import au.mainspring.nativeapp.niimbot.NiimbotAvailability
import au.mainspring.nativeapp.niimbot.PacketReassembler
import au.mainspring.nativeapp.niimbot.isNiimbotName
import au.mainspring.nativeapp.niimbot.niimbotIsTall
import au.mainspring.nativeapp.niimbot.niimbotRequiredPermissions
import au.mainspring.nativeapp.niimbot.niimbotTruncate
import au.mainspring.nativeapp.niimbot.niimbotUnavailableMessage
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private fun bytes(vararg v: Int) = ByteArray(v.size) { v[it].toByte() }
private fun ints(b: ByteArray) = b.map { it.toInt() and 0xff }

/** Vectors mirror frontend/src/lib/niimbot.test.ts. BLE I/O itself is not covered (no hardware). */
class NiimbotProtocolTest {
    @Test fun framesPacketWithHeaderLengthChecksumTrailer() {
        assertEquals(listOf(0x55, 0x55, 0x01, 0x01, 0x01, 0x01, 0xaa, 0xaa), ints(NiimbotProtocol.buildPacket(0x01, intArrayOf(0x01))))
    }

    @Test fun checksumIsXorOfCmdLenAndData() {
        val p = NiimbotProtocol.buildPacket(0x13, intArrayOf(0x00, 0xf0, 0x01, 0x90, 0x00, 0x02))
        assertEquals(0x76, p[p.size - 3].toInt() and 0xff)
        assertEquals(6, p[3].toInt())
        assertEquals(13, p.size)
    }

    @Test fun emptyPayload() {
        assertEquals(listOf(0x55, 0x55, 0xdc, 0x00, 0xdc, 0xaa, 0xaa), ints(NiimbotProtocol.buildPacket(0xdc, intArrayOf())))
    }

    @Test fun commandBuilders() {
        assertEquals(listOf(0x55, 0x55, 0x01, 0x02, 0x00, 0x03, 0x00, 0xaa, 0xaa), ints(NiimbotProtocol.startPrint(3)))
        // setDimension(height=240,width=400,copies=2) -> 00 f0 01 90 00 02
        assertEquals(listOf(0x00, 0xf0, 0x01, 0x90, 0x00, 0x02), ints(NiimbotProtocol.setDimension(240, 400, 2)).subList(4, 10))
        assertEquals(0x23, NiimbotProtocol.setLabelType()[2].toInt())
        assertEquals(0xf3, NiimbotProtocol.endPrint()[2].toInt() and 0xff)
    }

    @Test fun rasterRowKnownVector() {
        // 16x1: black at x=0 and x=15 -> bytes 80 01, thirds counts [1,0,1]
        val px = IntArray(16) { if (it == 0 || it == 15) 0xFF000000.toInt() else 0xFFFFFFFF.toInt() }
        val page = NiimbotProtocol.rasterize(px, 16, 1)
        assertEquals(1, page.rowPackets.size)
        assertEquals(
            listOf(0x55, 0x55, 0x85, 0x08, 0x00, 0x00, 0x01, 0x00, 0x01, 0x01, 0x80, 0x01, 0x0d, 0xaa, 0xaa),
            ints(page.rowPackets[0]),
        )
    }

    @Test fun rasterUsesRowIndexAndPadsPartialBytes() {
        // 10 wide (2 bytes/row), 3 rows; only row 2 has a black pixel at x=9 -> second byte 0x40
        val px = IntArray(30) { 0xFFFFFFFF.toInt() }
        px[2 * 10 + 9] = 0xFF000000.toInt()
        val page = NiimbotProtocol.rasterize(px, 10, 3)
        assertEquals(3, page.rowPackets.size)
        val row2 = ints(page.rowPackets[2])
        assertEquals(listOf(0x00, 0x02), row2.subList(4, 6)) // y u16
        assertEquals(0x40, row2[row2.size - 4]) // last data byte
        assertEquals(listOf(0, 0, 0), ints(page.rowPackets[0]).subList(6, 9)) // counts zero for a blank row
        assertEquals(15, page.rowPackets[0].size) // 8 data bytes + 7 framing
    }

    @Test fun thresholdsOnLuminance() {
        // dark grey (lum 100) prints, light grey (lum 200) does not; transparent-white default does not
        val px = intArrayOf(0xFF646464.toInt(), 0xFFC8C8C8.toInt())
        val d = ints(NiimbotProtocol.rasterize(px, 2, 1).rowPackets[0])
        assertEquals(0x80, d[10])
    }

    @Test fun batchRespectsMaxWriteAndKeepsPacketsWhole() {
        val packets = List(10) { ByteArray(100) { i -> (it + i).toByte() } }
        val batches = NiimbotProtocol.batchPackets(packets, 500)
        assertEquals(listOf(500, 500), batches.map { it.size })
        assertArrayEquals(packets.fold(ByteArray(0)) { a, p -> a + p }, batches.fold(ByteArray(0)) { a, b -> a + b })
        assertEquals(listOf(300), NiimbotProtocol.batchPackets(packets.take(3), 500).map { it.size })
    }

    @Test fun labelSizeFromRfid() {
        val data = ByteArray(40); data[33] = 50; data[34] = 70
        assertEquals(LabelDots(591, 827), NiimbotProtocol.labelDotsFromRfid(NiimbotPacket(0x1b, data)))
        assertEquals(NiimbotProtocol.DEFAULT_LABEL, LabelDots(591, 827))
        data[34] = 5
        assertNull(NiimbotProtocol.labelDotsFromRfid(NiimbotPacket(0x1b, data)))
        assertNull(NiimbotProtocol.labelDotsFromRfid(NiimbotPacket(0x1b, ByteArray(10))))
        assertNull(NiimbotProtocol.labelDotsFromRfid(null))
    }

    @Test fun printCompleteNeedsPageAndBothProgressBars() {
        fun reply(page: Int, a: Int, b: Int) = NiimbotPacket(0xb3, bytes(page shr 8, page and 0xff, a, b))
        assertTrue(NiimbotProtocol.printComplete(reply(2, 100, 100), 2))
        assertFalse(NiimbotProtocol.printComplete(reply(1, 100, 100), 2))
        assertFalse(NiimbotProtocol.printComplete(reply(2, 100, 50), 2))
        assertFalse(NiimbotProtocol.printComplete(NiimbotPacket(0xb3, bytes(0, 1)), 1))
    }

    @Test fun reassemblerHandlesSplitCoalescedAndCorruptFrames() {
        val a = NiimbotProtocol.buildPacket(0xdd, intArrayOf(1, 2, 3))
        val b = NiimbotProtocol.buildPacket(0x1b, intArrayOf(9))
        val r = PacketReassembler()
        assertEquals(0, r.feed(a.copyOfRange(0, 5)).size)
        val got = r.feed(a.copyOfRange(5, a.size) + b)
        assertEquals(listOf(0xdd, 0x1b), got.map { it.cmd })
        assertEquals(listOf(1, 2, 3), got[0].data.map { it.toInt() })
        // garbage prefix + bad checksum frame is skipped, good frame still decoded
        val bad = a.copyOf().also { it[it.size - 3] = (it[it.size - 3] + 1).toByte() }
        val got2 = PacketReassembler().feed(bytes(0x00, 0x13) + bad + b)
        assertEquals(listOf(0x1b), got2.map { it.cmd })
    }

    @Test fun permissionsDependOnSdk() {
        assertEquals(listOf("android.permission.BLUETOOTH_SCAN", "android.permission.BLUETOOTH_CONNECT"), niimbotRequiredPermissions(31))
        assertEquals(listOf("android.permission.BLUETOOTH_SCAN", "android.permission.BLUETOOTH_CONNECT"), niimbotRequiredPermissions(34))
        assertEquals(listOf("android.permission.ACCESS_FINE_LOCATION"), niimbotRequiredPermissions(30))
    }

    @Test fun deviceNamesAndLabelHelpers() {
        assertTrue(isNiimbotName("M2-1234")); assertTrue(isNiimbotName("My NIIMBOT")); assertFalse(isNiimbotName("JBL Speaker")); assertFalse(isNiimbotName(null))
        assertEquals("abc", niimbotTruncate("abc", 5)); assertEquals("abc…", niimbotTruncate("abcdefg", 4))
        assertTrue(niimbotIsTall(NiimbotProtocol.DEFAULT_LABEL)); assertFalse(niimbotIsTall(LabelDots(591, 354)))
    }

    @Test fun unavailableMessagesAreSpecific() {
        assertTrue(niimbotUnavailableMessage(NiimbotAvailability.BLUETOOTH_OFF).contains("turned off"))
        assertTrue(niimbotUnavailableMessage(NiimbotAvailability.PERMISSION_NEEDED).contains("permission"))
        assertTrue(niimbotUnavailableMessage(NiimbotAvailability.NO_BLUETOOTH_HARDWARE).contains("no Bluetooth"))
        assertTrue(NiimbotUiState.Done is NiimbotUiState)
    }

    // --- session lifecycle against a scripted fake printer -------------------------------------------------

    private class FakePrinter(override val canNotify: Boolean = true, override val writesAcknowledged: Boolean = true) : NiimbotTransport {
        val writes = mutableListOf<ByteArray>()
        private var listener: ((ByteArray) -> Unit)? = null
        var endAckAfter = 1
        private var endCalls = 0
        override fun setListener(listener: ((ByteArray) -> Unit)?) { this.listener = listener }
        override suspend fun write(bytes: ByteArray) {
            writes.add(bytes)
            if (!canNotify || bytes.size < 7 || bytes[0] != 0x55.toByte()) return
            val cmd = bytes[2].toInt() and 0xff
            when (cmd) {
                0x1a -> listener?.invoke(NiimbotProtocol.buildPacket(0x1b, IntArray(40).also { it[33] = 50; it[34] = 30 }))
                0xa3 -> listener?.invoke(NiimbotProtocol.buildPacket(0xb3, intArrayOf(0, 1, 100, 100)))
                0xf3 -> { endCalls++; listener?.invoke(NiimbotProtocol.buildPacket(0xf4, intArrayOf(if (endCalls >= endAckAfter) 1 else 0))) }
            }
        }
        fun cmds() = writes.filter { it.size >= 7 && it[0] == 0x55.toByte() && it[2] != 0x85.toByte() }.map { it[2].toInt() and 0xff }
    }

    @Test fun handshakeReadsLabelSize() = runBlocking {
        val printer = FakePrinter()
        val dots = NiimbotSession(printer) {}.handshake()
        assertEquals(LabelDots(591, 354), dots)
        assertEquals(listOf(0xdc, 0x1a), printer.cmds())
    }

    @Test fun printRunsFullLifecycleInOrder() = runBlocking {
        val printer = FakePrinter().apply { endAckAfter = 2 }
        val page = NiimbotProtocol.rasterize(IntArray(16 * 4) { 0xFFFFFFFF.toInt() }, 16, 4)
        NiimbotSession(printer) {}.print(listOf(page))
        // set type, density, start, page start, dimension, (rows), page end, status poll, end print x2 (first not acked)
        assertEquals(listOf(0x23, 0x21, 0x01, 0x03, 0x13, 0xe3, 0xa3, 0xf3, 0xf3), printer.cmds())
        val rowBytes = printer.writes.filter { it.size >= 3 && it[2] == 0x85.toByte() }.sumOf { it.size }
        assertEquals(page.rowPackets.sumOf { it.size }, rowBytes)
    }

    @Test fun printWithoutNotifyChannelStillSendsEverything() = runBlocking {
        val printer = FakePrinter(canNotify = false, writesAcknowledged = false)
        val pauses = mutableListOf<Long>()
        val page = NiimbotProtocol.rasterize(IntArray(8 * 8) { 0xFF000000.toInt() }, 8, 8)
        NiimbotSession(printer) { pauses.add(it) }.print(listOf(page))
        assertEquals(8, printer.writes.count { it.size >= 3 && it[2] == 0x85.toByte() }) // one write per row when unacknowledged
        assertTrue(pauses.any { it >= 2700 }) // fixed wait for the physical print instead of polling
    }
}
