import { memo, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function tableCells(line: string) {
  if (!/^ {0,3}\|.*\|\s*$/.test(line)) return []
  return line.trim().slice(1, -1).split(/(?<!\\)\|/).map(cell => cell.trim())
}

function recoverTableRows(markdown: string) {
  if (!markdown.includes('|n|')) return markdown
  let fence = ''
  let columns = 0
  let previous = ''
  return markdown.split('\n').map(line => {
    const marker = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line)
    if (marker && (!fence || (marker[1][0] === fence[0] &&
        marker[1].length >= fence.length && !marker[2].trim()))) {
      fence = fence ? '' : marker[1]
      previous = ''
      columns = 0
      return line
    }
    if (fence) return line
    const cells = tableCells(line)
    const header = tableCells(previous)
    previous = line
    if (cells.length && cells.length === header.length && cells.every(cell => /^:?-+:?$/.test(cell))) {
      columns = cells.length
      return line
    }
    if (columns && cells.length > columns && line.includes('|n|')) {
      const rows = line.replace(/(?<!\\)\|n\|/g, '|\n|').split('\n')
      if (rows.length > 1 && rows.every(row => tableCells(row).length === columns)) return rows.join('\n')
    }
    if (!cells.length) columns = 0
    return line
  }).join('\n')
}

export default memo(function MarkdownContent({ children }: { children?: ReactNode }) {
  const markdown = recoverTableRows(typeof children === 'string' ? children : String(children ?? ''))
  return <div className="capstone-chat-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ table: ({ children }) => <div className="capstone-chat-table-scroll"><table>{children}</table></div> }}>{markdown}</ReactMarkdown></div>
})
