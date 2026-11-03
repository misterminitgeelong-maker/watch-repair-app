package au.mainspring.nativeapp.niimbot

/**
 * Pure Niimbot wire-protocol helpers, ported from frontend/src/lib/niimbot.ts (Web Bluetooth).
 * No Android types here so everything is unit-testable on the JVM.
 *
 * Frame: 0x55 0x55 <cmd> <len> <data...> <xor> 0xAA 0xAA, xor over [cmd, len, data...].
 */
object NiimbotProtocol {
    const val SERVICE_UUID = "e7810a71-73ae-499d-8c15-faa9aef0c3f2"

    /** The M2 prints at 300 DPI (same constant as the web client). */
    const val DOTS_PER_MM = 300.0 / 25.4

    const val CMD_GET_RFID = 0x1a
    const val CMD_HEARTBEAT = 0xdc
    const val CMD_SET_LABEL_TYPE = 0x23
    const val CMD_SET_LABEL_DENSITY = 0x21
    const val CMD_START_PRINT = 0x01
    const val CMD_END_PRINT = 0xf3
    const val CMD_START_PAGE_PRINT = 0x03
    const val CMD_END_PAGE_PRINT = 0xe3
    const val CMD_SET_DIMENSION = 0x13
    const val CMD_GET_PRINT_STATUS = 0xa3
    /** Full bitmap row (row, 3 black-pixel counts, repeat, packed bits). 0x83 is the indexed format - do not use. */
    const val CMD_WRITE_IMAGE_ROW = 0x85

    fun dotsForMm(mm: Int): Int = Math.round(mm * DOTS_PER_MM).toInt()

    /** The shop's intake roll, 50x70mm, matching LABEL_50x70 on the web. */
    val DEFAULT_LABEL = LabelDots(dotsForMm(50), dotsForMm(70))

    fun buildPacket(cmd: Int, data: IntArray): ByteArray {
        require(data.size <= 255) { "Niimbot payload too long: ${data.size}" }
        val out = ByteArray(data.size + 7)
        out[0] = 0x55; out[1] = 0x55
        out[2] = cmd.toByte()
        out[3] = data.size.toByte()
        var xor = (cmd and 0xff) xor data.size
        for ((i, b) in data.withIndex()) {
            out[4 + i] = b.toByte()
            xor = xor xor (b and 0xff)
        }
        out[4 + data.size] = xor.toByte()
        out[5 + data.size] = 0xAA.toByte(); out[6 + data.size] = 0xAA.toByte()
        return out
    }

    fun heartbeat() = buildPacket(CMD_HEARTBEAT, intArrayOf(0x00))
    fun getRfid() = buildPacket(CMD_GET_RFID, intArrayOf(0x01))
    fun setLabelType() = buildPacket(CMD_SET_LABEL_TYPE, intArrayOf(0x01))
    fun setDensity(level: Int = 3) = buildPacket(CMD_SET_LABEL_DENSITY, intArrayOf(level))
    /** B1/M2 generation firmware: u16 total page count. */
    fun startPrint(totalPages: Int) = buildPacket(CMD_START_PRINT, intArrayOf((totalPages shr 8) and 0xff, totalPages and 0xff))
    fun startPage() = buildPacket(CMD_START_PAGE_PRINT, intArrayOf(0x01))
    /** rows (height), cols (width), copies - each u16. */
    fun setDimension(height: Int, width: Int, copies: Int) = buildPacket(
        CMD_SET_DIMENSION,
        intArrayOf((height shr 8) and 0xff, height and 0xff, (width shr 8) and 0xff, width and 0xff, (copies shr 8) and 0xff, copies and 0xff),
    )
    fun endPage() = buildPacket(CMD_END_PAGE_PRINT, intArrayOf(0x01))
    fun endPrint() = buildPacket(CMD_END_PRINT, intArrayOf(0x01))
    fun getPrintStatus() = buildPacket(CMD_GET_PRINT_STATUS, intArrayOf(0x01))

    /**
     * One 0x85 row packet per raster row. Pixels are ARGB ints (row-major); luminance < 128 prints black,
     * using the same weights as the web client. The three counts are black pixels per third of the head.
     */
    fun rasterize(pixels: IntArray, width: Int, height: Int): RasterPage {
        require(width > 0 && height > 0 && pixels.size >= width * height) { "Bad bitmap dimensions" }
        val bytesPerRow = (width + 7) / 8
        val packets = ArrayList<ByteArray>(height)
        for (y in 0 until height) {
            val data = IntArray(6 + bytesPerRow)
            data[0] = (y shr 8) and 0xff
            data[1] = y and 0xff
            data[5] = 0x01 // repeat count
            val counts = IntArray(3)
            for (x in 0 until width) {
                val p = pixels[y * width + x]
                val lum = 0.299 * ((p shr 16) and 0xff) + 0.587 * ((p shr 8) and 0xff) + 0.114 * (p and 0xff)
                if (lum < 128) {
                    data[6 + x / 8] = data[6 + x / 8] or (0x80 shr (x % 8))
                    counts[minOf(2, (x * 3) / width)]++
                }
            }
            data[2] = minOf(counts[0], 255); data[3] = minOf(counts[1], 255); data[4] = minOf(counts[2], 255)
            packets.add(buildPacket(CMD_WRITE_IMAGE_ROW, data))
        }
        return RasterPage(width, height, packets)
    }

    /** Concatenate row packets into writes of at most [maxWrite] bytes (web: 500). */
    fun batchPackets(packets: List<ByteArray>, maxWrite: Int = 500): List<ByteArray> {
        val out = ArrayList<ByteArray>()
        var cur = java.io.ByteArrayOutputStream()
        for (p in packets) {
            if (cur.size() + p.size > maxWrite && cur.size() > 0) { out.add(cur.toByteArray()); cur = java.io.ByteArrayOutputStream() }
            cur.write(p, 0, p.size)
        }
        if (cur.size() > 0) out.add(cur.toByteArray())
        return out
    }

    /**
     * Label size from a GET_RFID reply: 33 data bytes of uuid/barcode/serial/lengths/type, then width_mm, height_mm.
     * Implausible sizes are rejected (null) so a misparsed reply cannot produce a wrong canvas.
     */
    fun labelDotsFromRfid(reply: NiimbotPacket?): LabelDots? {
        val d = reply?.data ?: return null
        if (d.size < 35) return null
        val w = d[33].toInt() and 0xff
        val h = d[34].toInt() and 0xff
        if (w < 10 || w > 120 || h < 10 || h > 120) return null
        return LabelDots(dotsForMm(w), dotsForMm(h))
    }

    /** GET_PRINT_STATUS reply: u16 page, then two progress bytes. Done when page >= total and both >= 100. */
    fun printComplete(reply: NiimbotPacket, totalPages: Int): Boolean {
        val d = reply.data
        if (d.size < 4) return false
        val page = ((d[0].toInt() and 0xff) shl 8) or (d[1].toInt() and 0xff)
        return page >= totalPages && (d[2].toInt() and 0xff) >= 100 && (d[3].toInt() and 0xff) >= 100
    }
}

data class LabelDots(val width: Int, val height: Int)

class RasterPage(val width: Int, val height: Int, val rowPackets: List<ByteArray>)

class NiimbotPacket(val cmd: Int, val data: ByteArray)

/**
 * Reassembles notification fragments into whole packets. BLE notifications may split or coalesce frames;
 * resynchronises on the 0x55 0x55 header and drops frames with a bad checksum or trailer.
 */
class PacketReassembler {
    private var buf = ByteArray(0)

    fun feed(chunk: ByteArray): List<NiimbotPacket> {
        buf += chunk
        val out = ArrayList<NiimbotPacket>()
        while (true) {
            var start = -1
            for (i in 0 until buf.size - 1) if (buf[i] == 0x55.toByte() && buf[i + 1] == 0x55.toByte()) { start = i; break }
            if (start < 0) { buf = if (buf.isNotEmpty() && buf.last() == 0x55.toByte()) byteArrayOf(0x55) else ByteArray(0); break }
            if (start > 0) buf = buf.copyOfRange(start, buf.size)
            if (buf.size < 4) break
            val len = buf[3].toInt() and 0xff
            val total = len + 7
            if (buf.size < total) break
            val cmd = buf[2].toInt() and 0xff
            var xor = cmd xor len
            for (i in 0 until len) xor = xor xor (buf[4 + i].toInt() and 0xff)
            val ok = (buf[4 + len].toInt() and 0xff) == xor && buf[5 + len] == 0xAA.toByte() && buf[6 + len] == 0xAA.toByte()
            if (ok) {
                out.add(NiimbotPacket(cmd, buf.copyOfRange(4, 4 + len)))
                buf = buf.copyOfRange(total, buf.size)
            } else {
                buf = buf.copyOfRange(2, buf.size) // skip this header and resync
            }
        }
        return out
    }
}
