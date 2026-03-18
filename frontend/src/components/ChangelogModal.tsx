import { useState } from 'react'
import { X } from 'lucide-react'
import { Modal } from '@/components/ui'
import changelogData from '@/data/changelog.json'

type ChangelogEntry = { version: string; date: string; title: string; items: string[] }

export default function ChangelogModal({ onClose }: { onClose: () => void }) {
  const [entries] = useState<ChangelogEntry[]>(changelogData as ChangelogEntry[])

  return (
    <Modal title="What's new" onClose={onClose}>
      <div className="space-y-6 max-h-[70vh] overflow-y-auto">
        {entries.map((entry) => (
          <div key={entry.version}>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold" style={{ color: 'var(--cafe-text)' }}>v{entry.version}</span>
              <span className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{entry.date}</span>
            </div>
            <p className="text-sm mt-1" style={{ color: 'var(--cafe-text-mid)' }}>{entry.title}</p>
            <ul className="mt-2 list-disc list-inside text-sm space-y-1" style={{ color: 'var(--cafe-text)' }}>
              {entry.items.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Modal>
  )
}
