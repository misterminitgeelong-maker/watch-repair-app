package au.mainspring.nativeapp.ui

/**
 * Minimal dependency-free QR Code generator: byte mode, error correction level M, versions 1-10
 * (up to 213 bytes of UTF-8). Algorithm follows the public QR Code specification (ISO/IEC 18004).
 */
object QrCode {
    private const val MAX_VERSION = 10
    private val ECC_PER_BLOCK = intArrayOf(0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26)
    private val NUM_BLOCKS = intArrayOf(0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5)

    /** Returns the module matrix, indexed [row][column]; true is a dark module. */
    fun encode(text: String): Array<BooleanArray> {
        val bytes = text.toByteArray(Charsets.UTF_8)
        var version = 1
        while (true) {
            if (version > MAX_VERSION) throw IllegalArgumentException("Text too long for QR code")
            val capacityBits = dataCodewords(version) * 8
            val countBits = if (version < 10) 8 else 16
            if (4 + countBits + bytes.size * 8 <= capacityBits) break
            version++
        }
        val data = buildData(bytes, version)
        return Builder(version, addEccAndInterleave(data, version)).build()
    }

    private fun rawModules(ver: Int): Int {
        var r = (16 * ver + 128) * ver + 64
        if (ver >= 2) {
            val n = ver / 7 + 2
            r -= (25 * n - 10) * n - 55
            if (ver >= 7) r -= 36
        }
        return r
    }

    private fun dataCodewords(ver: Int) = rawModules(ver) / 8 - ECC_PER_BLOCK[ver] * NUM_BLOCKS[ver]

    private fun buildData(bytes: ByteArray, ver: Int): ByteArray {
        val bits = ArrayList<Int>()
        fun put(v: Int, n: Int) { for (i in n - 1 downTo 0) bits.add((v ushr i) and 1) }
        put(4, 4)
        put(bytes.size, if (ver < 10) 8 else 16)
        for (b in bytes) put(b.toInt() and 0xFF, 8)
        val cap = dataCodewords(ver) * 8
        put(0, minOf(4, cap - bits.size))
        while (bits.size % 8 != 0) bits.add(0)
        var pad = 0xEC
        while (bits.size < cap) { put(pad, 8); pad = pad xor 0xEC xor 0x11 }
        val out = ByteArray(bits.size / 8)
        for (i in bits.indices) out[i shr 3] = (out[i shr 3].toInt() or (bits[i] shl (7 - (i and 7)))).toByte()
        return out
    }

    private fun mul(x: Int, y: Int): Int {
        var z = 0
        for (i in 7 downTo 0) {
            z = (z shl 1) xor ((z ushr 7) * 0x11D)
            z = z xor (((y ushr i) and 1) * x)
        }
        return z
    }

    private fun divisor(degree: Int): IntArray {
        val r = IntArray(degree); r[degree - 1] = 1
        var root = 1
        repeat(degree) {
            for (j in 0 until degree) {
                r[j] = mul(r[j], root)
                if (j + 1 < degree) r[j] = r[j] xor r[j + 1]
            }
            root = mul(root, 2)
        }
        return r
    }

    private fun remainder(data: ByteArray, div: IntArray): IntArray {
        val r = IntArray(div.size)
        for (b in data) {
            val f = (b.toInt() and 0xFF) xor r[0]
            System.arraycopy(r, 1, r, 0, r.size - 1); r[r.size - 1] = 0
            for (i in r.indices) r[i] = r[i] xor mul(div[i], f)
        }
        return r
    }

    private fun addEccAndInterleave(data: ByteArray, ver: Int): ByteArray {
        val nb = NUM_BLOCKS[ver]; val eccLen = ECC_PER_BLOCK[ver]
        val raw = rawModules(ver) / 8
        val numShort = nb - raw % nb; val shortLen = raw / nb
        val div = divisor(eccLen)
        val blocks = ArrayList<IntArray>()
        var k = 0
        for (i in 0 until nb) {
            val datLen = shortLen - eccLen + (if (i < numShort) 0 else 1)
            val dat = data.copyOfRange(k, k + datLen); k += datLen
            val ecc = remainder(dat, div)
            val block = IntArray(shortLen + 1)
            for (j in dat.indices) block[j] = dat[j].toInt() and 0xFF
            // short blocks keep a zero placeholder at index shortLen - eccLen that is skipped on interleave
            val base = if (i < numShort) datLen + 1 else datLen
            for (j in ecc.indices) block[base + j] = ecc[j]
            blocks.add(block)
        }
        val out = ByteArray(raw); var n = 0
        for (i in 0..shortLen) for ((j, b) in blocks.withIndex()) {
            if (i != shortLen - eccLen || j >= numShort) { out[n++] = b[i].toByte() }
        }
        return out
    }

    private class Builder(val ver: Int, val codewords: ByteArray) {
        val size = ver * 4 + 17
        val m = Array(size) { BooleanArray(size) }
        val fn = Array(size) { BooleanArray(size) }

        fun build(): Array<BooleanArray> {
            drawFunctionPatterns()
            drawCodewords()
            var best = 0; var bestPenalty = Int.MAX_VALUE
            for (mask in 0 until 8) {
                applyMask(mask); drawFormat(mask)
                val p = penalty()
                if (p < bestPenalty) { best = mask; bestPenalty = p }
                applyMask(mask)
            }
            applyMask(best); drawFormat(best)
            return Array(size) { m[it].copyOf() }
        }

        fun set(x: Int, y: Int, dark: Boolean) { m[y][x] = dark; fn[y][x] = true }

        fun drawFunctionPatterns() {
            for (i in 0 until size) { set(6, i, i % 2 == 0); set(i, 6, i % 2 == 0) }
            finder(3, 3); finder(size - 4, 3); finder(3, size - 4)
            val pos = alignPositions()
            for (i in pos.indices) for (j in pos.indices) {
                if ((i == 0 && j == 0) || (i == 0 && j == pos.size - 1) || (i == pos.size - 1 && j == 0)) continue
                for (dy in -2..2) for (dx in -2..2) set(pos[i] + dx, pos[j] + dy, maxOf(Math.abs(dx), Math.abs(dy)) != 1)
            }
            drawFormat(0)
            if (ver >= 7) {
                var rem = ver
                repeat(12) { rem = (rem shl 1) xor ((rem ushr 11) * 0x1F25) }
                val bits = (ver shl 12) or rem
                for (i in 0 until 18) {
                    val c = ((bits ushr i) and 1) != 0
                    val a = size - 11 + i % 3; val b = i / 3
                    set(a, b, c); set(b, a, c)
                }
            }
        }

        fun alignPositions(): IntArray {
            if (ver == 1) return IntArray(0)
            val n = ver / 7 + 2
            val step = (ver * 4 + n * 2 + 1) / (n * 2 - 2) * 2
            val r = IntArray(n); r[0] = 6
            var p = size - 7
            for (i in n - 1 downTo 1) { r[i] = p; p -= step }
            return r
        }

        fun finder(cx: Int, cy: Int) {
            for (dy in -4..4) for (dx in -4..4) {
                val d = maxOf(Math.abs(dx), Math.abs(dy)); val x = cx + dx; val y = cy + dy
                if (x in 0 until size && y in 0 until size) set(x, y, d != 2 && d != 4)
            }
        }

        fun drawFormat(mask: Int) {
            val data = mask // error correction level M is 0b00
            var rem = data
            repeat(10) { rem = (rem shl 1) xor ((rem ushr 9) * 0x537) }
            val bits = ((data shl 10) or rem) xor 0x5412
            fun bit(i: Int) = ((bits ushr i) and 1) != 0
            for (i in 0..5) set(8, i, bit(i))
            set(8, 7, bit(6)); set(8, 8, bit(7)); set(7, 8, bit(8))
            for (i in 9..14) set(14 - i, 8, bit(i))
            for (i in 0..7) set(size - 1 - i, 8, bit(i))
            for (i in 8..14) set(8, size - 15 + i, bit(i))
            set(8, size - 8, true)
        }

        fun drawCodewords() {
            var i = 0
            var right = size - 1
            while (right >= 1) {
                if (right == 6) right = 5
                for (vert in 0 until size) for (j in 0..1) {
                    val x = right - j
                    val up = ((right + 1) and 2) == 0
                    val y = if (up) size - 1 - vert else vert
                    if (!fn[y][x] && i < codewords.size * 8) {
                        m[y][x] = ((codewords[i shr 3].toInt() ushr (7 - (i and 7))) and 1) != 0
                        i++
                    }
                }
                right -= 2
            }
        }

        fun applyMask(mask: Int) {
            for (y in 0 until size) for (x in 0 until size) {
                val inv = when (mask) {
                    0 -> (x + y) % 2 == 0
                    1 -> y % 2 == 0
                    2 -> x % 3 == 0
                    3 -> (x + y) % 3 == 0
                    4 -> (x / 3 + y / 2) % 2 == 0
                    5 -> x * y % 2 + x * y % 3 == 0
                    6 -> (x * y % 2 + x * y % 3) % 2 == 0
                    else -> ((x + y) % 2 + x * y % 3) % 2 == 0
                }
                if (!fn[y][x] && inv) m[y][x] = !m[y][x]
            }
        }

        /** Simplified penalty (runs, 2x2 blocks, dark balance); any mask is valid, this just picks a good one. */
        fun penalty(): Int {
            var p = 0
            for (pass in 0..1) for (a in 0 until size) {
                var run = 1
                for (b in 1 until size) {
                    val cur = if (pass == 0) m[a][b] else m[b][a]
                    val prev = if (pass == 0) m[a][b - 1] else m[b - 1][a]
                    if (cur == prev) { run++; if (run == 5) p += 3 else if (run > 5) p++ } else run = 1
                }
            }
            for (y in 0 until size - 1) for (x in 0 until size - 1) {
                val c = m[y][x]
                if (c == m[y][x + 1] && c == m[y + 1][x] && c == m[y + 1][x + 1]) p += 3
            }
            val dark = m.sumOf { row -> row.count { it } }
            val total = size * size
            p += ((Math.abs(dark * 20 - total * 10) + total - 1) / total - 1) * 10
            return p
        }
    }
}
