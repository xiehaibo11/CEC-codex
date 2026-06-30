import ReactMarkdown from 'react-markdown'

interface MarkdownDisplayProps {
  content: string
  variant?: 'summary' | 'full'
}

export function MarkdownDisplay({ content, variant = 'summary' }: MarkdownDisplayProps) {
  const className = variant === 'full'
    ? 'prose prose-sm md:prose-base max-w-none break-words'
    : 'prose prose-sm max-w-none'

  return (
    <div className={className}>
      <ReactMarkdown>
        {content}
      </ReactMarkdown>
    </div>
  )
}
