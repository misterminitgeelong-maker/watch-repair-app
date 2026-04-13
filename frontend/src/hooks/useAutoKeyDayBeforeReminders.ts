import { useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listAutoKeyJobs, sendAutoKeyDayBeforeReminders } from '@/lib/api'

function ymdLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function useAutoKeyDayBeforeReminders() {
  const qc = useQueryClient()
  const tomorrowYmd = useMemo(() => {
    const d = new Date()
    d.setDate(d.getDate() + 1)
    return ymdLocal(d)
  }, [])

  const { data: tomorrowJobs = [] } = useQuery({
    queryKey: ['auto-key-jobs', 'tomorrow-count', tomorrowYmd],
    queryFn: () => listAutoKeyJobs({ date_from: tomorrowYmd, date_to: tomorrowYmd }).then(r => r.data),
    staleTime: 60_000,
  })

  const sendRemindersMut = useMutation({
    mutationFn: () => sendAutoKeyDayBeforeReminders().then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auto-key-reports'] }),
  })

  return { tomorrowYmd, tomorrowJobs, sendRemindersMut }
}
