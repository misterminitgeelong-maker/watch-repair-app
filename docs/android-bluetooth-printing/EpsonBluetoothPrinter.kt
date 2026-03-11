package com.mainspring.print

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import java.io.IOException
import java.nio.charset.Charset
import kotlin.math.min
import java.util.UUID

class EpsonBluetoothPrinter(private val context: Context) {

    private var socket: BluetoothSocket? = null

    companion object {
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
        private val ASCII: Charset = Charsets.US_ASCII

        // ESC/POS commands
        private val INIT = byteArrayOf(0x1B, 0x40)
        private val ALIGN_LEFT = byteArrayOf(0x1B, 0x61, 0x00)
        private val ALIGN_CENTER = byteArrayOf(0x1B, 0x61, 0x01)
        private val BOLD_ON = byteArrayOf(0x1B, 0x45, 0x01)
        private val BOLD_OFF = byteArrayOf(0x1B, 0x45, 0x00)
        private val DOUBLE_HEIGHT_ON = byteArrayOf(0x1D, 0x21, 0x01)
        private val DOUBLE_HEIGHT_OFF = byteArrayOf(0x1D, 0x21, 0x00)
        private val CUT_PAPER = byteArrayOf(0x1D, 0x56, 0x42, 0x00) // GS V 66 0
        private val UTF8: Charset = Charsets.UTF_8
    }

    @Throws(PrinterException::class)
    fun connect(device: BluetoothDevice) {
        ensureBluetoothPermission()

        val adapter = BluetoothAdapter.getDefaultAdapter()
            ?: throw PrinterException("Bluetooth not supported on this device")

        if (!adapter.isEnabled) {
            throw PrinterException("Bluetooth is disabled")
        }

        if (device.bondState != BluetoothDevice.BOND_BONDED) {
            throw PrinterException("Printer is not paired. Pair printer in Bluetooth settings first.")
        }

        close()

        try {
            adapter.cancelDiscovery()
            val candidate = try {
                device.createRfcommSocketToServiceRecord(SPP_UUID)
            } catch (_: Exception) {
                device.createInsecureRfcommSocketToServiceRecord(SPP_UUID)
            }
            candidate.connect()
            socket = candidate
        } catch (e: IOException) {
            close()
            throw PrinterException("Failed to connect to printer ${device.name ?: device.address}", e)
        }
    }

    @Throws(PrinterException::class)
    fun printReceipt(receiptData: ReceiptData) {
        val body = buildDualCopyEscPos(receiptData)
        printRawEscPos(body)
    }

    @Throws(PrinterException::class)
    fun printRawEscPos(rawBytes: ByteArray) {
        val out = socket?.outputStream
            ?: throw PrinterException("Printer is not connected")

        try {
            out.write(rawBytes)
            out.flush()
        } catch (e: IOException) {
            throw PrinterException("Failed to write to printer", e)
        }
    }

    fun close() {
        try {
            socket?.close()
        } catch (_: IOException) {
            // no-op
        } finally {
            socket = null
        }
    }

    fun getPairedEpsonTmM30iiPrinters(): List<BluetoothDevice> {
        ensureBluetoothPermission()
        val adapter = BluetoothAdapter.getDefaultAdapter() ?: return emptyList()
        return adapter.bondedDevices
            .filter { it.name?.contains("TM-m30", ignoreCase = true) == true || it.name?.contains("Epson", ignoreCase = true) == true }
            .sortedBy { it.name ?: it.address }
    }

    private fun buildDualCopyEscPos(data: ReceiptData): ByteArray {
        val bytes = ArrayList<Byte>()

        fun append(raw: ByteArray) = raw.forEach { bytes.add(it) }
        fun appendLine(text: String = "") = append((text + "\n").toByteArray(ASCII))
        fun divider() = appendLine("--------------------------------")
        fun appendQrCode(content: String) {
            if (content.isBlank()) return

            val payload = content.toByteArray(UTF8)
            // Epson QR: max storable bytes per command is limited.
            val maxPayload = min(payload.size, 700)
            val dataBytes = payload.copyOf(maxPayload)

            val storeLen = dataBytes.size + 3
            val pL = (storeLen and 0xFF).toByte()
            val pH = ((storeLen shr 8) and 0xFF).toByte()

            // Select model 2
            append(byteArrayOf(0x1D, 0x28, 0x6B, 0x04, 0x00, 0x31, 0x41, 0x32, 0x00))
            // Set module size (1..16)
            append(byteArrayOf(0x1D, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x43, 0x06))
            // Set error correction level M
            append(byteArrayOf(0x1D, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x45, 0x31))
            // Store QR data
            append(byteArrayOf(0x1D, 0x28, 0x6B, pL, pH, 0x31, 0x50, 0x30))
            append(dataBytes)
            // Print QR symbol
            append(byteArrayOf(0x1D, 0x28, 0x6B, 0x03, 0x00, 0x31, 0x51, 0x30))
        }

        // ---- WORKSHOP COPY ----
        append(INIT)
        append(ALIGN_CENTER)
        append(BOLD_ON)
        append(DOUBLE_HEIGHT_ON)
        appendLine(data.appName)
        append(DOUBLE_HEIGHT_OFF)
        append(BOLD_OFF)

        appendLine("WORKSHOP COPY")
        divider()

        append(ALIGN_LEFT)
        appendLine("Job Number: ${data.jobNumber}")
        appendLine("Customer: ${data.customerName}")
        appendLine("Phone: ${data.phone}")
        appendLine("Item Type: ${data.itemType}")
        appendLine("Description: ${data.repairDescription}")
        appendLine("Price: ${data.price}")
        appendLine("Status: ${data.status}")
        appendLine("Created: ${data.createdDate}")

        if (data.notes.isNotBlank()) {
            divider()
            appendLine("Notes:")
            data.notes.lines().forEach { appendLine(it) }
        }

        divider()
        append(ALIGN_CENTER)
        appendLine("Internal job QR")
        if (data.internalJobUrl.isNotBlank()) {
            appendQrCode(data.internalJobUrl)
            appendLine("Scan for workshop job details")
        } else {
            appendLine("QR unavailable")
            appendLine("Internal link missing")
        }
        append(ALIGN_LEFT)

        divider()
        append(ALIGN_CENTER)
        appendLine("Internal workshop ticket")
        appendLine()
        appendLine()

        append(CUT_PAPER)

        // ---- CUSTOMER COPY ----
        append(INIT)
        append(ALIGN_CENTER)
        append(BOLD_ON)
        append(DOUBLE_HEIGHT_ON)
        appendLine(data.appName)
        append(DOUBLE_HEIGHT_OFF)
        append(BOLD_OFF)

        appendLine("CUSTOMER COPY")
        divider()

        append(ALIGN_LEFT)
        appendLine("Job Number: ${data.jobNumber}")
        appendLine("Customer: ${data.customerName}")
        appendLine("Phone: ${data.phone}")
        appendLine("Item Type: ${data.itemType}")
        appendLine("Repair: ${data.repairDescription}")
        appendLine("Status: ${data.status}")
        appendLine("Created: ${data.createdDate}")

        divider()
        appendLine("Price Breakdown")
        appendLine("Estimated Repair: ${data.price}")
        if (data.deposit.isNotBlank()) {
            appendLine("Deposit Paid: ${data.deposit}")
        }
        if (data.estimatedBalance.isNotBlank()) {
            appendLine("Estimated Balance: ${data.estimatedBalance}")
        }

        if (data.notes.isNotBlank()) {
            divider()
            appendLine("Notes:")
            data.notes.lines().forEach { appendLine(it) }
        }

        divider()
        append(ALIGN_CENTER)
        appendLine("Track repair updates")
        if (data.customerStatusUrl.isNotBlank()) {
            appendQrCode(data.customerStatusUrl)
            appendLine("Scan for live status updates")
        } else {
            appendLine("QR unavailable")
            appendLine("Status link missing")
        }
        append(ALIGN_LEFT)

        divider()
        append(ALIGN_CENTER)
        appendLine("Thank you for choosing Mainspring")
        appendLine("Keep this receipt for pickup")
        appendLine()
        appendLine()

        append(CUT_PAPER)

        return bytes.toByteArray()
    }

    private fun ensureBluetoothPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return

        val hasConnect = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.BLUETOOTH_CONNECT
        ) == PackageManager.PERMISSION_GRANTED

        if (!hasConnect) {
            throw PrinterException("Missing BLUETOOTH_CONNECT permission")
        }
    }
}

class PrinterException(message: String, cause: Throwable? = null) : Exception(message, cause)
