const ONBOARDING_CHECKLIST_KEY_PREFIX = 'onboarding-checklist-dismissed:'

function keyForTenant(tenantId: string | null): string {
  return `${ONBOARDING_CHECKLIST_KEY_PREFIX}${tenantId ?? 'unknown'}`
}

export function isChecklistDismissed(tenantId: string | null): boolean {
  if (!tenantId) return false
  return localStorage.getItem(keyForTenant(tenantId)) === '1'
}

export function setChecklistDismissed(tenantId: string | null, dismissed: boolean): void {
  if (!tenantId) return
  if (dismissed) {
    localStorage.setItem(keyForTenant(tenantId), '1')
  } else {
    localStorage.removeItem(keyForTenant(tenantId))
  }
}
