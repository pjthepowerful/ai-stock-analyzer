import { useState } from 'react'
import { useChats } from '../../lib/chats'
import { useChrome } from '../../lib/chrome'

export function ChatList() {
  const { chats, active, select, create, remove, scan } = useChats()
  const { openPlus } = useChrome()
  const [confirming, setConfirming] = useState<string | null>(null)

  return (
    <aside className="chat-list" aria-label="Chats">
      <button
        className="chat-list-new"
        onClick={() => {
          if (!create()) openPlus()
        }}
      >
        + New chat
      </button>

      <ul className="chat-list-items">
        {chats.map((c) => (
          <li key={c.id} className={'chat-list-item' + (c.id === active?.id ? ' chat-list-item-on' : '')}>
            {confirming === c.id ? (
              <div className="chat-list-confirm">
                <span>Delete?</span>
                <button
                  className="chat-list-yes"
                  onClick={() => {
                    remove(c.id)
                    setConfirming(null)
                  }}
                >
                  yes
                </button>
                <button className="chat-list-no" onClick={() => setConfirming(null)}>
                  no
                </button>
              </div>
            ) : (
              <>
                <button className="chat-list-title" onClick={() => select(c.id)} title={c.title}>
                  {scan?.chatId === c.id && <span className="chat-list-live" aria-label="Scan running" />}
                  {c.title}
                </button>
                <button className="chat-list-del" onClick={() => setConfirming(c.id)} aria-label={`Delete ${c.title}`}>
                  ×
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </aside>
  )
}
