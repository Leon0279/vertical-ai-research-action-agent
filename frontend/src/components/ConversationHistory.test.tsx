import { HttpResponse, http } from 'msw';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { server } from '../test/server';
import { renderWithProviders } from '../test/render';
import { ConversationHistory } from './ConversationHistory';

describe('ConversationHistory', () => {
  it('prepends older pages, de-duplicates messages, and renders all content formats safely', async () => {
    server.use(
      http.get(
        'http://localhost/api/v1/conversations/session-1/messages',
        ({ request }) => {
          const cursor = new URL(request.url).searchParams.get('cursor');
          if (cursor) {
            return HttpResponse.json({
              session_id: 'session-1',
              messages: [
                {
                  message_id: 'message-1',
                  role: 'user',
                  content: '最早的问题',
                  content_format: 'text',
                  created_at: '2026-09-20T08:00:00Z',
                },
                {
                  message_id: 'message-2',
                  role: 'user',
                  content: '当前问题',
                  content_format: 'text',
                  created_at: '2026-09-20T09:00:00Z',
                },
              ],
              next_cursor: null,
            });
          }
          return HttpResponse.json({
            session_id: 'session-1',
            messages: [
              {
                message_id: 'message-2',
                role: 'user',
                content: '当前问题',
                content_format: 'text',
                created_at: '2026-09-20T09:00:00Z',
              },
              {
                message_id: 'message-3',
                role: 'assistant',
                content: '# 回答标题\n<script>unsafe</script>\n**安全正文**',
                content_format: 'markdown',
                created_at: '2026-09-20T09:01:00Z',
                assistant_details: {
                  summary: '回答摘要',
                  recommendation: '采用方案 A',
                  confidence: 0.82,
                  action_items: [
                    {
                      title: '制作原型',
                      description: '验证主流程',
                      priority: 'high',
                      metadata: {},
                    },
                  ],
                  citations: [
                    { source: 'https://example.com', note: '示例来源' },
                  ],
                  caveats: ['样本有限'],
                },
              },
              {
                message_id: 'message-4',
                role: 'system',
                content: '{"ok":true}',
                content_format: 'json',
                created_at: '2026-09-20T09:02:00Z',
              },
              {
                message_id: 'message-5',
                role: 'tool',
                content: '工具执行完成',
                content_format: 'text',
                created_at: '2026-09-20T09:03:00Z',
              },
            ],
            next_cursor: 'older-page',
          });
        },
      ),
    );

    const user = userEvent.setup();
    const { container } = renderWithProviders(
      <ConversationHistory userId="user-1" sessionId="session-1" />,
    );

    expect(await screen.findByRole('heading', { name: '回答标题' })).toBeInTheDocument();
    expect(screen.getByText('安全正文')).toBeInTheDocument();
    expect(screen.queryByText('unsafe')).not.toBeInTheDocument();
    expect(container.querySelector('script')).not.toBeInTheDocument();
    expect(screen.getByText('工具执行完成')).toBeInTheDocument();
    expect(container.querySelector('.conversation-json')).toHaveTextContent('"ok": true');

    await user.click(screen.getByText('查看结构化详情'));
    expect(screen.getByText('回答摘要')).toBeInTheDocument();
    expect(screen.getByText('采用方案 A')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getByText('制作原型')).toBeInTheDocument();
    expect(screen.getByText('样本有限')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /加载更早消息/ }));
    expect(await screen.findByText('最早的问题')).toBeInTheDocument();
    expect(screen.getAllByText('当前问题')).toHaveLength(1);
    const messages = [...container.querySelectorAll('.conversation-message')];
    expect(messages[0]).toHaveTextContent('最早的问题');
    expect(messages[1]).toHaveTextContent('当前问题');
  });

  it('shows stable API errors and offers retry', async () => {
    server.use(
      http.get(
        'http://localhost/api/v1/conversations/missing/messages',
        () =>
          HttpResponse.json(
            {
              error_code: 'CONVERSATION_SESSION_NOT_FOUND',
              error_reason: '未找到指定会话。',
            },
            { status: 404 },
          ),
      ),
    );

    renderWithProviders(
      <ConversationHistory userId="user-1" sessionId="missing" />,
    );

    expect(await screen.findByText(/未找到指定会话/)).toBeInTheDocument();
    expect(screen.getByText(/HTTP 404 · CONVERSATION_SESSION_NOT_FOUND/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /重新加载/ })).toBeInTheDocument();
  });
});
