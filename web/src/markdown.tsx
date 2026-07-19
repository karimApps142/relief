// A small, dependency-free Markdown renderer for assistant replies.
//
// Deliberately not react-markdown: this app ships zero runtime dependencies beyond React
// (see web/package.json), and web/dist is committed, so every dep is weight the GPU box
// has to pull. The subset below is what a chat model actually emits — fenced code,
// headings, lists, tables, blockquotes, and inline emphasis/code/links.
//
// Input is always treated as text: nothing here renders raw HTML, so model output cannot
// inject markup into the page.
import { useState, type ReactNode } from 'react'
import { Icon } from './icons'

// ---------------------------------------------------------------- inline (spans)
const INLINE = /(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|(?<!\*)\*[^*\n]+\*|__[^_]+__|~~[^~]+~~|`[^`\n]+`|\[[^\]]*\]\([^)\s]+\)|https?:\/\/[^\s<>()]+)/g

function inline(text: string, keyPrefix = ''): ReactNode[] {
  const out: ReactNode[] = []
  let i = 0
  for (const part of text.split(INLINE)) {
    if (!part) continue
    const k = `${keyPrefix}i${i++}`
    if (part.startsWith('***') && part.endsWith('***')) {
      out.push(<strong key={k}><em>{part.slice(3, -3)}</em></strong>)
    } else if ((part.startsWith('**') && part.endsWith('**')) || (part.startsWith('__') && part.endsWith('__'))) {
      out.push(<strong key={k} style={{ fontWeight: 650 }}>{part.slice(2, -2)}</strong>)
    } else if (part.startsWith('~~') && part.endsWith('~~')) {
      out.push(<span key={k} style={{ textDecoration: 'line-through', opacity: 0.7 }}>{part.slice(2, -2)}</span>)
    } else if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      out.push(<em key={k}>{part.slice(1, -1)}</em>)
    } else if (part.startsWith('`') && part.endsWith('`')) {
      out.push(
        <code key={k} style={{
          font: '500 0.88em var(--hf-font-mono)', background: 'var(--hf-fill-medium)',
          padding: '.14em .4em', borderRadius: 5, whiteSpace: 'break-spaces',
        }}>{part.slice(1, -1)}</code>,
      )
    } else if (part.startsWith('[')) {
      const m = /^\[([^\]]*)\]\(([^)\s]+)\)$/.exec(part)
      out.push(m
        ? <a key={k} href={m[2]} target="_blank" rel="noreferrer noopener"
            style={{ color: 'var(--hf-info)', textDecoration: 'underline', textUnderlineOffset: 2 }}>{m[1] || m[2]}</a>
        : <span key={k}>{part}</span>)
    } else if (/^https?:\/\//.test(part)) {
      out.push(
        <a key={k} href={part} target="_blank" rel="noreferrer noopener"
          style={{ color: 'var(--hf-info)', textDecoration: 'underline', textUnderlineOffset: 2, wordBreak: 'break-all' }}>{part}</a>,
      )
    } else {
      out.push(<span key={k}>{part}</span>)
    }
  }
  return out
}

// ---------------------------------------------------------------- code block
export function CodeBlock({ code, lang }: { code: string; lang?: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    }).catch(() => { /* clipboard blocked (insecure origin) — the text stays selectable */ })
  }
  return (
    <div style={{ margin: '12px 0', borderRadius: 12, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 34, padding: '0 8px 0 13px', borderBottom: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)' }}>
        <span style={{ font: '600 11px var(--hf-font-mono)', letterSpacing: '.04em', color: 'var(--hf-text-tertiary)', textTransform: 'uppercase' }}>{lang || 'code'}</span>
        <button onClick={copy} className="rs-hover" title="Copy code"
          style={{ display: 'flex', alignItems: 'center', gap: 5, height: 24, padding: '0 8px', borderRadius: 7, border: 'none', background: 'transparent', cursor: 'pointer', font: '600 11.5px var(--hf-font-sans)', color: copied ? 'var(--hf-accent)' : 'var(--hf-text-secondary)' }}>
          <Icon name={copied ? 'check' : 'copy'} size={13} sw={2} />{copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre style={{ margin: 0, padding: '12px 14px', overflowX: 'auto', font: '400 12.5px/1.65 var(--hf-font-mono)', color: 'var(--hf-text-primary)' }}>
        <code>{code}</code>
      </pre>
    </div>
  )
}

// ---------------------------------------------------------------- block parsing
type Block =
  | { t: 'code'; code: string; lang?: string }
  | { t: 'h'; level: number; text: string }
  | { t: 'ul' | 'ol'; items: string[]; start?: number }
  | { t: 'quote'; lines: string[] }
  | { t: 'table'; head: string[]; rows: string[][] }
  | { t: 'hr' }
  | { t: 'p'; text: string }

const cells = (row: string) => row.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())

function parse(src: string): Block[] {
  const lines = src.replace(/\r\n?/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // fenced code — an unterminated fence (mid-stream) still renders what arrived
    const fence = /^\s*```+\s*(\S+)?\s*$/.exec(line)
    if (fence) {
      const body: string[] = []
      i++
      while (i < lines.length && !/^\s*```+\s*$/.test(lines[i])) body.push(lines[i++])
      i++
      blocks.push({ t: 'code', code: body.join('\n'), lang: fence[1] })
      continue
    }
    if (!line.trim()) { i++; continue }

    const h = /^(#{1,6})\s+(.*)$/.exec(line)
    if (h) { blocks.push({ t: 'h', level: h[1].length, text: h[2] }); i++; continue }

    if (/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)) { blocks.push({ t: 'hr' }); i++; continue }

    // table: a header row followed by a |---|---| separator
    if (line.includes('|') && /^\s*\|?[\s:-]*\|[\s|:-]*$/.test(lines[i + 1] || '')) {
      const head = cells(line)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) rows.push(cells(lines[i++]))
      blocks.push({ t: 'table', head, rows })
      continue
    }

    const ul = /^\s*[-*+]\s+(.*)$/.exec(line)
    const ol = /^\s*(\d+)[.)]\s+(.*)$/.exec(line)
    if (ul || ol) {
      const ordered = !!ol
      const items: string[] = []
      const start = ol ? Number(ol[1]) : undefined
      while (i < lines.length) {
        const m = ordered ? /^\s*\d+[.)]\s+(.*)$/.exec(lines[i]) : /^\s*[-*+]\s+(.*)$/.exec(lines[i])
        if (m) { items.push(m[1]); i++; continue }
        // a plain indented line continues the previous item
        if (items.length && /^\s{2,}\S/.test(lines[i])) { items[items.length - 1] += ' ' + lines[i].trim(); i++; continue }
        break
      }
      blocks.push({ t: ordered ? 'ol' : 'ul', items, start })
      continue
    }

    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = []
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) quote.push(lines[i++].replace(/^\s*>\s?/, ''))
      blocks.push({ t: 'quote', lines: quote })
      continue
    }

    // paragraph — consume until a blank line or the start of another block
    const para: string[] = []
    while (i < lines.length && lines[i].trim()
      && !/^\s*```/.test(lines[i]) && !/^#{1,6}\s/.test(lines[i])
      && !/^\s*[-*+]\s/.test(lines[i]) && !/^\s*\d+[.)]\s/.test(lines[i])
      && !/^\s*>/.test(lines[i])) para.push(lines[i++])
    blocks.push({ t: 'p', text: para.join('\n') })
  }
  return blocks
}

// ---------------------------------------------------------------- render
const H_SIZE = [0, 20, 17.5, 15.5, 14.5, 14, 13.5]

export function Markdown({ text }: { text: string }) {
  const blocks = parse(text)
  return (
    <div style={{ font: '400 14.5px/1.72 var(--hf-font-sans)', color: 'var(--hf-text-primary)' }}>
      {blocks.map((b, n) => {
        const k = `b${n}`
        switch (b.t) {
          case 'code':
            return <CodeBlock key={k} code={b.code} lang={b.lang} />
          case 'h':
            return (
              <div key={k} style={{ font: `650 ${H_SIZE[b.level]}px var(--hf-font-sans)`, letterSpacing: '-.01em', margin: n === 0 ? '0 0 8px' : '20px 0 8px' }}>
                {inline(b.text, k)}
              </div>
            )
          case 'hr':
            return <hr key={k} style={{ border: 0, borderTop: '1px solid var(--hf-border)', margin: '18px 0' }} />
          case 'ul':
          case 'ol': {
            const Tag = b.t === 'ol' ? 'ol' : 'ul'
            return (
              <Tag key={k} start={b.start} style={{ margin: '8px 0', paddingLeft: 22, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {b.items.map((it, m) => <li key={m} style={{ paddingLeft: 2 }}>{inline(it, `${k}-${m}`)}</li>)}
              </Tag>
            )
          }
          case 'quote':
            return (
              <blockquote key={k} style={{ margin: '12px 0', padding: '2px 0 2px 14px', borderLeft: '3px solid var(--hf-border-strong)', color: 'var(--hf-text-secondary)' }}>
                {inline(b.lines.join('\n'), k)}
              </blockquote>
            )
          case 'table':
            return (
              <div key={k} style={{ margin: '12px 0', overflowX: 'auto', borderRadius: 10, border: '1px solid var(--hf-border)' }}>
                <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13.5 }}>
                  <thead>
                    <tr>{b.head.map((c, m) => (
                      <th key={m} style={{ textAlign: 'left', padding: '9px 12px', font: '600 12.5px var(--hf-font-sans)', color: 'var(--hf-text-secondary)', background: 'var(--hf-surface-2)', borderBottom: '1px solid var(--hf-border)', whiteSpace: 'nowrap' }}>{inline(c, `${k}h${m}`)}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {b.rows.map((row, m) => (
                      <tr key={m}>{row.map((c, q) => (
                        <td key={q} style={{ padding: '9px 12px', borderTop: m ? '1px solid var(--hf-border-subtle)' : 'none', verticalAlign: 'top' }}>{inline(c, `${k}r${m}c${q}`)}</td>
                      ))}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          default:
            return <p key={k} style={{ margin: n === 0 ? '0 0 10px' : '10px 0', whiteSpace: 'pre-wrap' }}>{inline(b.text, k)}</p>
        }
      })}
    </div>
  )
}
