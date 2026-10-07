import { Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

export default function ThreadSystemNotice({ tone = 'info', children, instruction, action, onAction }: {
  tone?: 'info' | 'error'; children: ReactNode; instruction?: string; action?: string; onAction?: () => void
}) {
  return <div className={`capstone-system-notice is-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
    {tone === 'error' ? <TriangleAlert aria-hidden="true" /> : <Info aria-hidden="true" />}
    <div><span className="capstone-system-label">系统提示</span>
      {instruction && <p className="capstone-system-instruction">相关指令：{instruction}</p>}
      <div className="capstone-system-text">{children}</div>
      {action && onAction && <button type="button" onClick={onAction}>{action}</button>}
    </div>
  </div>
}
