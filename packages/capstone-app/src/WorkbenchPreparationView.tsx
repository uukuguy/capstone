import { Check, Circle, LoaderCircle } from 'lucide-react'
import type { PreparationUpdate } from './workbenchPreparation'

const labels: Record<string, string> = {
  api: '连接工作台', database: '会话与历史记录',
  'worker:pandapower': 'pandapower 计算工具', 'worker:pypsa': 'PyPSA 计算工具',
  worker: '计算工具',
}
const statuses = { waiting: '等待准备', preparing: '准备中', ready: '已就绪', failed: '暂未就绪' }

export default function WorkbenchPreparation({ updates, error, onRetry, compact = false }: {
  updates: PreparationUpdate[]; error: string | null; onRetry: () => void; compact?: boolean
}) {
  return <div className={compact ? 'workbench-preparation-compact' : 'workbench-preparation-shell'}>
    <section className="workbench-preparation" aria-label="工作台准备进度" aria-busy={!error}>
      <span className="eyebrow">CAPSTONE</span>
      <h1>{compact ? '正在恢复连接' : '正在准备工作台'}</h1>
      <p className="workbench-preparation-intro">{compact
        ? '当前内容已保留，就绪后即可继续操作。'
        : '准备完成后将自动进入，首次连接可能需要稍候。'}</p>
      <ol aria-live="polite" aria-relevant="text">
        {updates.map(item => <li key={item.component} data-state={item.status}>
          {item.status === 'ready' ? <Check size={16} aria-hidden="true" />
            : item.status === 'preparing' ? <LoaderCircle size={16} className="preparation-spinner" aria-hidden="true" />
              : <Circle size={12} aria-hidden="true" />}
          <span>{labels[item.component] || '计算工具'}</span>
          <small>{statuses[item.status]}</small>
        </li>)}
      </ol>
      {error && <div className="workbench-preparation-error"><p role="alert">{error}</p>
        <button type="button" onClick={onRetry}>重试连接</button></div>}
    </section>
  </div>
}
