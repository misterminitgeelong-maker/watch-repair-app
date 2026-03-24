# Android Epson TM-m30II Bluetooth Printing (ESC/POS)

This folder contains drop-in Kotlin code for direct Bluetooth ESC/POS printing to Epson TM-m30II printers.

## What this gives you

- No Android system print dialog
- Direct Bluetooth printing with ESC/POS bytes
- Support for paired Epson TM-m30II devices
- Reusable helper class with required methods:
  - `connect(device)`
  - `printReceipt(receiptData)`
  - `printRawEscPos(rawBytes)`
  - `close()`
- Runtime permission handling for:
  - `BLUETOOTH_CONNECT`
  - `BLUETOOTH_SCAN`
- Example print flow from repair details screen
- Receipt includes all requested fields + paper cut command
- Prints two tickets in one print run:
  - workshop copy
  - customer copy (with price breakdown)

## Files

- `ReceiptData.kt`
- `EpsonBluetoothPrinter.kt`
- `BluetoothPermissionHelper.kt`
- `RepairDetailsPrintFlow.kt`

## AndroidManifest permissions

Add these in your app manifest:

```xml
<uses-permission android:name="android.permission.BLUETOOTH" android:maxSdkVersion="30" />
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN" android:maxSdkVersion="30" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
<uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
```

## Integration checklist

1. Copy Kotlin files into your Android app module package (for example `com.mainspring.print`).
2. Replace example `RepairDetailsActivity` wiring with your real repair details screen.
3. Map your real repair data into `ReceiptData`.
4. Ensure printer is paired in Android Bluetooth settings.
5. Request Bluetooth runtime permissions before listing/connecting.
6. Print on background thread (`Dispatchers.IO`) as shown.

## Notes

- Epson TM Utility can print while your app cannot if your app is using wrong transport.
- This helper uses Bluetooth SPP + ESC/POS direct socket transport.
- The cut command is included: `GS V 66 0`.
- `printReceipt(receiptData)` outputs workshop copy first, then customer copy.
- QR support is built in:
  - `internalJobUrl` prints on workshop copy (internal data side)
  - `customerStatusUrl` prints on customer copy (customer updates side)
