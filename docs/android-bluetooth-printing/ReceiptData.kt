package com.mainspring.print

data class ReceiptData(
    val appName: String = "Mainspring",
    val jobNumber: String,
    val customerName: String,
    val phone: String,
    val itemType: String,
    val repairDescription: String,
    val price: String,
    val deposit: String = "",
    val estimatedBalance: String = "",
    val status: String,
    val createdDate: String,
    val notes: String = "",
    val internalJobUrl: String = "",
    val customerStatusUrl: String = ""
)
