import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AgentResult } from './AgentResult';

describe('AgentResult', () => {
  it('renders structured output and does not inject raw HTML', () => {
    const { container } = render(
      <AgentResult
        result={{
          trace_id: 'trace-123',
          task_type: 'recommendation',
          workflow_pattern: 'recommendation',
          answer: '# 安全标题\n<script>window.bad = true</script>\n**正文**',
          summary: '摘要内容',
          recommendation: '优先实施方案 A',
          action_items: [
            { title: '制作原型', priority: 'high', metadata: {} },
          ],
          citations: [{ source: 'https://example.com', note: '示例来源' }],
          confidence: 0.84,
          caveats: ['样本有限'],
          stage_history: ['planning', 'research', 'output'],
          metadata: { iterations: 2 },
        }}
      />,
    );

    expect(screen.getByRole('heading', { name: '安全标题' })).toBeInTheDocument();
    expect(screen.getByText('优先实施方案 A')).toBeInTheDocument();
    expect(screen.getByText('84%')).toBeInTheDocument();
    expect(container.querySelector('script')).not.toBeInTheDocument();
  });
});
