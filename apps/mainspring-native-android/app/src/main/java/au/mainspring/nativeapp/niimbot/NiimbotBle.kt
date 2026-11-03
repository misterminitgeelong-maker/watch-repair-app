package au.mainspring.nativeapp.niimbot

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import java.io.IOException
import java.util.UUID

/*
 * Android BLE I/O for Niimbot printers. NOT VERIFIED ON HARDWARE: the protocol layer (NiimbotProtocol,
 * NiimbotSession) is unit-tested, but the GATT plumbing below has never talked to a real printer.
 */

/** Runtime permissions needed to scan and connect for a given SDK level. */
fun niimbotRequiredPermissions(sdk: Int): List<String> =
    if (sdk >= Build.VERSION_CODES.S) listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
    else listOf(Manifest.permission.ACCESS_FINE_LOCATION) // pre-12: BLE scans need location; BLUETOOTH/ADMIN are install-time

/** Same name test as the web client (namePrefix 'M2'), plus any device advertising a Niimbot name. */
fun isNiimbotName(name: String?): Boolean = name != null && (name.startsWith("M2") || name.contains("niimbot", ignoreCase = true))

data class NiimbotDevice(val name: String, val address: String)

enum class NiimbotAvailability { READY, NO_BLUETOOTH_HARDWARE, BLUETOOTH_OFF, PERMISSION_NEEDED }

fun niimbotMissingPermissions(context: Context): List<String> =
    niimbotRequiredPermissions(Build.VERSION.SDK_INT).filter { ContextCompat.checkSelfPermission(context, it) != PackageManager.PERMISSION_GRANTED }

fun niimbotAvailability(context: Context): NiimbotAvailability {
    if (!context.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) return NiimbotAvailability.NO_BLUETOOTH_HARDWARE
    val adapter = (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter
        ?: return NiimbotAvailability.NO_BLUETOOTH_HARDWARE
    if (niimbotMissingPermissions(context).isNotEmpty()) return NiimbotAvailability.PERMISSION_NEEDED
    return if (adapter.isEnabled) NiimbotAvailability.READY else NiimbotAvailability.BLUETOOTH_OFF
}

private fun adapterOf(context: Context): BluetoothAdapter? = (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter

/** Already-paired Niimbot printers (shown immediately while scanning continues). Requires BLUETOOTH_CONNECT. */
@SuppressLint("MissingPermission")
fun niimbotBondedDevices(context: Context): List<NiimbotDevice> = try {
    adapterOf(context)?.bondedDevices.orEmpty().filter { isNiimbotName(it.name) }.map { NiimbotDevice(it.name, it.address) }
} catch (e: SecurityException) { emptyList() }

/** Emits distinct Niimbot devices found by a BLE scan until the collector cancels. Requires scan permission. */
@SuppressLint("MissingPermission")
fun niimbotScan(context: Context): Flow<NiimbotDevice> = callbackFlow {
    val scanner = adapterOf(context)?.bluetoothLeScanner
    if (scanner == null) { close(IOException("Bluetooth scanner unavailable")); return@callbackFlow }
    val seen = HashSet<String>()
    val cb = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val name = try { result.device.name } catch (e: SecurityException) { null } ?: result.scanRecord?.deviceName
            if (isNiimbotName(name) && seen.add(result.device.address)) trySend(NiimbotDevice(name.orEmpty(), result.device.address))
        }
        override fun onScanFailed(errorCode: Int) { close(IOException("Bluetooth scan failed (code $errorCode)")) }
    }
    try {
        scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), cb)
    } catch (e: SecurityException) { close(e); return@callbackFlow }
    awaitClose { try { scanner.stopScan(cb) } catch (_: Exception) {} }
}

/** An open GATT connection exposing the Niimbot service as a [NiimbotTransport]. */
@SuppressLint("MissingPermission")
class NiimbotBleTransport private constructor(private val gatt: BluetoothGatt, private val handler: GattHandler) : NiimbotTransport {
    class GattHandler : BluetoothGattCallback() {
        var listener: ((ByteArray) -> Unit)? = null
        val connected = CompletableDeferred<Unit>()
        val mtuChanged = CompletableDeferred<Int>()
        val servicesDiscovered = CompletableDeferred<Unit>()
        val descriptorWritten = CompletableDeferred<Unit>()
        @Volatile var pendingWrite: CompletableDeferred<Int>? = null
        @Volatile var disconnected = false

        override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) connected.complete(Unit)
            else if (newState == BluetoothProfile.STATE_DISCONNECTED || status != BluetoothGatt.GATT_SUCCESS) {
                disconnected = true
                val err = IOException("Printer disconnected (status $status)")
                connected.completeExceptionally(err); servicesDiscovered.completeExceptionally(err); descriptorWritten.completeExceptionally(err)
                pendingWrite?.completeExceptionally(err)
            }
        }
        override fun onMtuChanged(gatt: BluetoothGatt, mtu: Int, status: Int) { mtuChanged.complete(if (status == BluetoothGatt.GATT_SUCCESS) mtu else 23) }
        override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
            if (status == BluetoothGatt.GATT_SUCCESS) servicesDiscovered.complete(Unit) else servicesDiscovered.completeExceptionally(IOException("Service discovery failed ($status)"))
        }
        override fun onDescriptorWrite(gatt: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) { descriptorWritten.complete(Unit) }
        override fun onCharacteristicWrite(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, status: Int) {
            val p = pendingWrite
            if (status == BluetoothGatt.GATT_SUCCESS) p?.complete(status) else p?.completeExceptionally(IOException("BLE write failed ($status)"))
        }
        @Deprecated("Used before API 33")
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) @Suppress("DEPRECATION") characteristic.value?.let { listener?.invoke(it) }
        }
        override fun onCharacteristicChanged(gatt: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) { listener?.invoke(value) }
    }

    private var writeChar: BluetoothGattCharacteristic? = null
    private var mtu = 23
    private var withResponse = true
    private var notify = false
    private val writeLock = Mutex()

    override val canNotify get() = notify
    override val writesAcknowledged get() = withResponse
    override fun setListener(listener: ((ByteArray) -> Unit)?) { handler.listener = listener }

    override suspend fun write(bytes: ByteArray) = writeLock.withLock {
        val ch = writeChar ?: throw IOException("Not connected to printer")
        val chunkSize = (mtu - 3).coerceAtLeast(20)
        var offset = 0
        while (offset < bytes.size) {
            if (handler.disconnected) throw IOException("Printer disconnected")
            val chunk = bytes.copyOfRange(offset, minOf(bytes.size, offset + chunkSize))
            val type = if (withResponse) BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT else BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            var attempts = 0
            while (true) {
                val ack = if (withResponse) CompletableDeferred<Int>().also { handler.pendingWrite = it } else null
                val started = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    gatt.writeCharacteristic(ch, chunk, type) == BluetoothGatt.GATT_SUCCESS
                } else {
                    @Suppress("DEPRECATION") run { ch.writeType = type; ch.value = chunk; gatt.writeCharacteristic(ch) }
                }
                if (started) { if (ack != null) withTimeout(5000) { ack.await() }; break }
                if (++attempts >= 20) throw IOException("BLE write rejected by the stack")
                delay(15) // stack busy
            }
            offset += chunk.size
        }
    }

    fun close() { handler.listener = null; try { gatt.disconnect(); gatt.close() } catch (_: Exception) {} }

    companion object {
        private val CCCD: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

        /** Connect, negotiate MTU, discover the Niimbot service, enable notifications. Throws IOException on failure. */
        suspend fun connect(context: Context, address: String): NiimbotBleTransport {
            val adapter = adapterOf(context) ?: throw IOException("Bluetooth is not available")
            val device: BluetoothDevice = try { adapter.getRemoteDevice(address) } catch (e: IllegalArgumentException) { throw IOException("Invalid printer address") }
            val handler = GattHandler()
            val gatt = device.connectGatt(context.applicationContext, false, handler, BluetoothDevice.TRANSPORT_LE) ?: throw IOException("Could not start a connection")
            val t = NiimbotBleTransport(gatt, handler)
            try {
                withTimeout(15000) { handler.connected.await() }
                gatt.requestMtu(247)
                t.mtu = try { withTimeout(3000) { handler.mtuChanged.await() } } catch (e: Exception) { 23 }
                gatt.discoverServices()
                withTimeout(10000) { handler.servicesDiscovered.await() }
                val service = gatt.getService(UUID.fromString(NiimbotProtocol.SERVICE_UUID)) ?: throw IOException("This device is not a Niimbot printer")
                val chars = service.characteristics
                val writable = chars.firstOrNull { it.properties and (BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0 }
                    ?: throw IOException("No writable characteristic on the printer")
                t.writeChar = writable
                t.withResponse = writable.properties and BluetoothGattCharacteristic.PROPERTY_WRITE != 0
                val notifiable = chars.firstOrNull { it.properties and (BluetoothGattCharacteristic.PROPERTY_NOTIFY or BluetoothGattCharacteristic.PROPERTY_INDICATE) != 0 }
                if (notifiable != null) {
                    gatt.setCharacteristicNotification(notifiable, true)
                    val cccd = notifiable.getDescriptor(CCCD)
                    if (cccd != null) {
                        val enable = if (notifiable.properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0) BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE else BluetoothGattDescriptor.ENABLE_INDICATION_VALUE
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) gatt.writeDescriptor(cccd, enable)
                        else @Suppress("DEPRECATION") run { cccd.value = enable; gatt.writeDescriptor(cccd) }
                        withTimeout(5000) { handler.descriptorWritten.await() }
                    }
                    t.notify = true
                }
                return t
            } catch (e: Exception) {
                t.close()
                if (e is kotlinx.coroutines.CancellationException && e !is kotlinx.coroutines.TimeoutCancellationException) throw e
                throw if (e is IOException) e else IOException(e.message ?: "Could not connect to the printer", e)
            }
        }
    }
}
