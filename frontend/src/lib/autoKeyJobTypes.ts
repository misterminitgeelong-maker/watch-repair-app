/** Auto Key / Mobile Services job type options for dropdowns and reports */
export const AUTO_KEY_JOB_TYPES = [
  'Key Cutting (in-store)',
  'Transponder Programming',
  'Lockout – Car',
  'Lockout – Boot/Trunk',
  'Lockout – Roadside',
  'All Keys Lost',
  'Remote / Fob Sync',
  'Ignition Repair',
  'Ignition Replace',
  'Duplicate Key',
  'Broken Key Extraction',
  'Door Lock Change',
  'Diagnostic',
] as const

export type AutoKeyJobType = (typeof AUTO_KEY_JOB_TYPES)[number] | ''
