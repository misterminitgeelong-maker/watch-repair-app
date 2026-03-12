const ONBOARDING_CHECKLIST_KEY_PREFIX = 'onboarding-checklist-dismissed:'
const DEMO_MODE_KEY = 'mainspring_demo_mode_enabled'
const PAGE_TUTORIAL_SEEN_PREFIX = 'mainspring_page_tutorial_seen:'

function keyForTenant(tenantId: string | null): string {
  return `${ONBOARDING_CHECKLIST_KEY_PREFIX}${tenantId ?? 'unknown'}`
}

function tutorialSeenKey(tenantId: string | null, pageKey: string): string {
  return `${PAGE_TUTORIAL_SEEN_PREFIX}${tenantId ?? 'unknown'}:${pageKey}`
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

export function enableDemoMode(enabled: boolean): void {
  if (enabled) {
    localStorage.setItem(DEMO_MODE_KEY, '1')
  } else {
    localStorage.removeItem(DEMO_MODE_KEY)
  }
}

export function isDemoModeEnabled(): boolean {
  return localStorage.getItem(DEMO_MODE_KEY) === '1'
}

export function hasSeenPageTutorial(tenantId: string | null, pageKey: string): boolean {
  return localStorage.getItem(tutorialSeenKey(tenantId, pageKey)) === '1'
}

export function setPageTutorialSeen(tenantId: string | null, pageKey: string, seen: boolean): void {
  const key = tutorialSeenKey(tenantId, pageKey)
  if (seen) {
    localStorage.setItem(key, '1')
  } else {
    localStorage.removeItem(key)
  }
}

export function resetPageTutorials(tenantId: string | null): void {
  const tenantPrefix = `${PAGE_TUTORIAL_SEEN_PREFIX}${tenantId ?? 'unknown'}:`
  const keys = Object.keys(localStorage)
  for (const key of keys) {
    if (key.startsWith(tenantPrefix)) {
      localStorage.removeItem(key)
    }
  }
}

export function resetAllPageTutorials(): void {
  const keys = Object.keys(localStorage)
  for (const key of keys) {
    if (key.startsWith(PAGE_TUTORIAL_SEEN_PREFIX)) {
      localStorage.removeItem(key)
    }
  }
}
