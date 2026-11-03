package au.mainspring.nativeapp

data class QuickItem(val label: String,val description: String,val cents: Int,val category: String)
/** Mirrors the web quick-item catalogue; only enabled shop categories are displayed. */
val MOBILE_QUICK_ITEMS = listOf(
    QuickItem("Callout \u2013 min charge","30km radius",5000,"general_service"),
    QuickItem("Callout \u2013 next 30km","Additional distance band",5000,"general_service"),
    QuickItem("Gain entry","Callout charged separately",10000,"general_service"),
    QuickItem("Lishi pick & decode","Incl. callout",25000,"vehicle_key"),
    QuickItem("Diagnostic fee","Callout charged separately",10000,"general_service"),
    QuickItem("Transponder copy","Callout charged separately",9000,"vehicle_key"),
    QuickItem("Transponder gen/prog","Incl. callout",25000,"vehicle_key"),
    QuickItem("Cut and prog","Customer supplied key",25000,"vehicle_key"),
    QuickItem("All keys lost \u2013 TE","TE key, no remote",30000,"vehicle_key"),
    QuickItem("All keys lost \u2013 Basic","Manual remote code chip from car",38000,"vehicle_key"),
    QuickItem("All keys lost \u2013 Prox","Proximity key",48000,"vehicle_key"),
    QuickItem("Lock rekey","Per lock",15000,"general_service"),
    QuickItem("Smart cable prog","Nissan/Renault/Toyota/Chrysler, incl. callout",65000,"vehicle_key"),
    QuickItem("Door service","Lubricate and tighten fasteners",22000,"garage_door"),
    QuickItem("Weather seal","Replace bottom rubber weather seal",40000,"garage_door"),
    QuickItem("Door lock","Replace roller/tilt lock",35000,"garage_door"),
    QuickItem("Cables","Replace cables both sides",33000,"garage_door"),
    QuickItem("Hinge replacement","Replace broken hinges",17500,"garage_door"),
    QuickItem("Spring re-tension","Tension and balance door",15000,"garage_door"),
    QuickItem("Wheel replacement","Replace broken wheels",17500,"garage_door"),
    QuickItem("Motor calibration","Reset limits and sensitivity",15000,"garage_door"),
    QuickItem("Spring replacement","Replace spring assembly",45000,"garage_door"),
    QuickItem("Motor replacement","Swap out motor",80000,"garage_door"),
)
data class QuoteBundle(val label: String,val note: String,val lines: List<QuoteLineDraft>)
private fun presetLine(description: String,price: String) = QuoteLineDraft(description=description,price=price)
/** Editable retail baselines from frontend/src/lib/autoKeyJobTypes.ts. AUD only. */
val MOBILE_QUOTE_BUNDLES = listOf(
    QuoteBundle("All Keys Lost (full)","Supply & program + diagnostic",listOf(presetLine("All keys lost - supply & program","449"),presetLine("Automotive key / immobiliser diagnostic","159"))),
    QuoteBundle("Lockout + new key","Vehicle lockout + duplicate key",listOf(presetLine("Vehicle lockout service","189"),presetLine("Duplicate key - cut & program","89"))),
    QuoteBundle("Ignition replace (full)","Ignition + programming + diagnostic",listOf(presetLine("Ignition replacement","349"),presetLine("Transponder programming","120"),presetLine("Automotive key / immobiliser diagnostic","159"))),
    QuoteBundle("Broken key recovery","Extraction + duplicate key",listOf(presetLine("Broken key extraction","129"),presetLine("Duplicate key - cut & program","89"))),
)
