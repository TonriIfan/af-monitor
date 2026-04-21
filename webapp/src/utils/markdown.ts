function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function sanitizeUrl(url: string) {
  return /^https?:\/\//i.test(url) ? url : ''
}

function renderInlineMarkdown(input: string) {
  const codeTokens: string[] = []
  let text = escapeHtml(input).replace(/`([^`]+)`/g, (_, code: string) => {
    const token = `__CODE_TOKEN_${codeTokens.length}__`
    codeTokens.push(`<code>${code}</code>`)
    return token
  })

  text = text
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label: string, url: string) => {
      const safeUrl = sanitizeUrl(url)
      if (!safeUrl) return label
      return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`
    })
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<]+)/g, (_, prefix: string, url: string) => {
      const safeUrl = sanitizeUrl(url)
      if (!safeUrl) return `${prefix}${url}`
      return `${prefix}<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${url}</a>`
    })

  return codeTokens.reduce(
    (result, html, index) => result.replaceAll(`__CODE_TOKEN_${index}__`, html),
    text,
  )
}

export function renderMarkdown(input: string) {
  const lines = input.replace(/\r\n/g, '\n').split('\n')
  const blocks: string[] = []
  let paragraph: string[] = []
  let listItems: string[] = []
  let listTag: 'ul' | 'ol' | '' = ''
  let quoteLines: string[] = []
  let codeLines: string[] = []
  let inCodeBlock = false

  function flushParagraph() {
    if (!paragraph.length) return
    blocks.push(`<p>${renderInlineMarkdown(paragraph.join('<br />'))}</p>`)
    paragraph = []
  }

  function flushList() {
    if (!listItems.length || !listTag) return
    blocks.push(`<${listTag}>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</${listTag}>`)
    listItems = []
    listTag = ''
  }

  function flushQuote() {
    if (!quoteLines.length) return
    blocks.push(`<blockquote><p>${renderInlineMarkdown(quoteLines.join('<br />'))}</p></blockquote>`)
    quoteLines = []
  }

  function flushCode() {
    if (!codeLines.length) return
    blocks.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
    codeLines = []
  }

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      flushParagraph()
      flushList()
      flushQuote()
      if (inCodeBlock) {
        flushCode()
      }
      inCodeBlock = !inCodeBlock
      continue
    }

    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }

    const trimmed = line.trim()
    if (!trimmed) {
      flushParagraph()
      flushList()
      flushQuote()
      continue
    }

    const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/)
    if (headingMatch) {
      flushParagraph()
      flushList()
      flushQuote()
      const level = Math.min(4, headingMatch[1].length)
      blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`)
      continue
    }

    const quoteMatch = trimmed.match(/^>\s?(.*)$/)
    if (quoteMatch) {
      flushParagraph()
      flushList()
      quoteLines.push(quoteMatch[1])
      continue
    }

    const unorderedMatch = trimmed.match(/^[-*+]\s+(.+)$/)
    if (unorderedMatch) {
      flushParagraph()
      flushQuote()
      if (listTag && listTag !== 'ul') flushList()
      listTag = 'ul'
      listItems.push(unorderedMatch[1])
      continue
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/)
    if (orderedMatch) {
      flushParagraph()
      flushQuote()
      if (listTag && listTag !== 'ol') flushList()
      listTag = 'ol'
      listItems.push(orderedMatch[1])
      continue
    }

    flushList()
    flushQuote()
    paragraph.push(trimmed)
  }

  if (inCodeBlock) flushCode()
  flushParagraph()
  flushList()
  flushQuote()

  return blocks.join('')
}
