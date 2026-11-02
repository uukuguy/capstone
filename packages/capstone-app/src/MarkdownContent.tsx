import { memo, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default memo(function MarkdownContent({ children }: { children?: ReactNode }) {
  return <div className="capstone-chat-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ table: ({ children }) => <div className="capstone-chat-table-scroll"><table>{children}</table></div> }}>{typeof children === 'string' ? children : String(children ?? '')}</ReactMarkdown></div>
})
