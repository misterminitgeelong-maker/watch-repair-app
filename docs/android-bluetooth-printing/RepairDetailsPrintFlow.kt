package com.mainspring.print

import android.bluetooth.BluetoothDevice
import android.os.Bundle
import android.widget.Button
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Example flow for a Repair Details screen.
 * Wire this into your existing screen and map your real Repair model fields.
 */
class RepairDetailsActivity : AppCompatActivity() {

    private lateinit var printer: EpsonBluetoothPrinter

    private val bluetoothPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        val allGranted = grants.values.all { it }
        if (!allGranted) {
            Toast.makeText(this, "Bluetooth permissions are required for printing", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // setContentView(R.layout.activity_repair_details)

        printer = EpsonBluetoothPrinter(this)

        val printButton = Button(this).apply { text = "Print Receipt" }
        setContentView(printButton)

        printButton.setOnClickListener {
            BluetoothPermissionHelper.requestIfNeeded(this, bluetoothPermissionLauncher)
            if (!BluetoothPermissionHelper.hasRequiredPermissions(this)) {
                return@setOnClickListener
            }
            startPrintFlow()
        }
    }

    private fun startPrintFlow() {
        val pairedPrinters = try {
            printer.getPairedEpsonTmM30iiPrinters()
        } catch (e: Exception) {
            Toast.makeText(this, e.message ?: "Unable to load paired printers", Toast.LENGTH_LONG).show()
            return
        }

        if (pairedPrinters.isEmpty()) {
            Toast.makeText(
                this,
                "No paired Epson TM-m30II printers found. Pair printer in Bluetooth settings first.",
                Toast.LENGTH_LONG
            ).show()
            return
        }

        showPrinterChooser(pairedPrinters)
    }

    private fun showPrinterChooser(devices: List<BluetoothDevice>) {
        val labels = devices.map { "${it.name ?: "Unknown"} (${it.address})" }.toTypedArray()

        AlertDialog.Builder(this)
            .setTitle("Select Printer")
            .setItems(labels) { _, index ->
                connectAndPrint(devices[index])
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun connectAndPrint(device: BluetoothDevice) {
        val receipt = ReceiptData(
            appName = "Mainspring",
            jobNumber = "JOB-00123",
            customerName = "Jane Smith",
            phone = "0400 000 000",
            itemType = "Watch",
            repairDescription = "Service + crystal replacement",
            price = "$180.00",
            deposit = "$50.00",
            estimatedBalance = "$130.00",
            status = "awaiting_collection",
            createdDate = "2026-03-11",
            notes = "Customer requested careful polishing.",
            internalJobUrl = "https://mainspring.au/jobs/JOB-00123",
            customerStatusUrl = "https://mainspring.au/status/abc123status"
        )

        lifecycleScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    printer.connect(device)
                    printer.printReceipt(receipt)
                }
                Toast.makeText(this@RepairDetailsActivity, "Receipt printed", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                Toast.makeText(
                    this@RepairDetailsActivity,
                    e.message ?: "Printing failed",
                    Toast.LENGTH_LONG
                ).show()
            } finally {
                withContext(Dispatchers.IO) {
                    printer.close()
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        printer.close()
    }
}
