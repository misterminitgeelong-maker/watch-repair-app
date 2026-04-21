import { useState } from 'react'
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
              <span className="font-semibold" style={{ color: 'var(--ms-text)' }}>v{entry.version}</span>
              <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>{entry.date}</span>
            </div>
            <p className="text-sm mt-1" style={{ color: 'var(--ms-text-mid)' }}>{entry.title}</p>
            <ul className="mt-2 list-disc list-inside text-sm space-y-1" style={{ color: 'var(--ms-text)' }}>
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
