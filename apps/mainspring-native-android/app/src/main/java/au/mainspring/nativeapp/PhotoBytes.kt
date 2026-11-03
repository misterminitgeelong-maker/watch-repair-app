package au.mainspring.nativeapp

import java.io.ByteArrayOutputStream
import java.io.InputStream

/** Bound allocation before reading arbitrary document-provider content. Works on API 26. */
internal fun readPhotoBounded(stream: InputStream, maxBytes: Int = 10 * 1024 * 1024): ByteArray {
    val output = ByteArrayOutputStream()
    val buffer = ByteArray(8192)
    var total = 0
    while (true) {
        val count = stream.read(buffer)
        if (count < 0) break
        total += count
        require(total <= maxBytes) { "Photo exceeds 10 MB." }
        output.write(buffer, 0, count)
    }
    return output.toByteArray()
}
