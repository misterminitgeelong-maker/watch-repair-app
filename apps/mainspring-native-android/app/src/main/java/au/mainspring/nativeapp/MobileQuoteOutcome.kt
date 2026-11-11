package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.MobileQuote

/** An option quote has no fixed invoice total until the technician confirms an available outcome. */
fun MobileQuote.needsOutcomeChoice(): Boolean = !options.isNullOrEmpty() && options.none { it.key == selectedOption }
