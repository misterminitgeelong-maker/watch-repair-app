package au.mainspring.nativeapp

import au.mainspring.nativeapp.api.RepairJobRead
/** Customer quote, matching web job cards and header. */
fun watchQuoteCents(job: RepairJobRead): Int = if(job.costCents > 0) job.costCents else job.preQuoteCents
