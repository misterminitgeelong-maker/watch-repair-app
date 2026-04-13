import { useState } from 'react'

export function useMobileServicesModals() {
  const [showCreate, setShowCreate] = useState(false)
  const [showAddTech, setShowAddTech] = useState(false)
  const [showCommissionRules, setShowCommissionRules] = useState(false)
  const [showMoreActions, setShowMoreActions] = useState(false)
  const [plannerDetailJobId, setPlannerDetailJobId] = useState<string | null>(null)

  return {
    showCreate,
    setShowCreate,
    showAddTech,
    setShowAddTech,
    showCommissionRules,
    setShowCommissionRules,
    showMoreActions,
    setShowMoreActions,
    plannerDetailJobId,
    setPlannerDetailJobId,
  }
}
