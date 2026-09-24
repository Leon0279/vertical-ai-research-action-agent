import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from '../test/server';
import { api } from './services';

describe('typed API services', () => {
  it('sends the complete Agent request payload', async () => {
    server.use(
      http.post('http://localhost/api/v1/agent/run', async ({ request }) => {
        const body = await request.json();
        expect(body).toEqual({
          query: '比较两个方案',
          user_id: 'user-1',
          session_id: 'session-1',
          project_id: 'project-1',
          iteration_budget: 3,
        });
        return HttpResponse.json({
          trace_id: 'trace-1',
          task_type: 'comparison',
          workflow_pattern: 'comparison',
          answer: '结果',
          summary: '摘要',
          recommendation: null,
          action_items: [],
          citations: [],
          confidence: 0.8,
          caveats: [],
          stage_history: ['task_interpretation', 'output'],
          metadata: {},
        });
      }),
    );

    const result = await api.runAgent({
      query: '比较两个方案',
      user_id: 'user-1',
      session_id: 'session-1',
      project_id: 'project-1',
      iteration_budget: 3,
    });

    expect(result.trace_id).toBe('trace-1');
    expect(result.stage_history).toEqual(['task_interpretation', 'output']);
  });

  it('serializes repeated action filters and cursor pagination', async () => {
    server.use(
      http.get('http://localhost/api/v1/memories/actions', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('user_id')).toBe('user-1');
        expect(url.searchParams.get('project_id')).toBe('project-1');
        expect(url.searchParams.get('cursor')).toBe('cursor-2');
        expect(url.searchParams.getAll('action_status')).toEqual([
          'todo',
          'blocked',
        ]);
        return HttpResponse.json({
          project_id: 'project-1',
          items: [],
          next_cursor: null,
        });
      }),
    );

    const page = await api.actions(
      'user-1',
      'project-1',
      ['todo', 'blocked'],
      'cursor-2',
    );
    expect(page.next_cursor).toBeNull();
  });

  it('serializes conversation list and message cursor requests', async () => {
    server.use(
      http.get('http://localhost/api/v1/conversations', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('user_id')).toBe('user-1');
        expect(url.searchParams.get('limit')).toBe('20');
        expect(url.searchParams.get('cursor')).toBe('session-cursor');
        return HttpResponse.json({ sessions: [], next_cursor: null });
      }),
      http.get(
        'http://localhost/api/v1/conversations/session-1/messages',
        ({ request }) => {
          const url = new URL(request.url);
          expect(url.searchParams.get('user_id')).toBe('user-1');
          expect(url.searchParams.get('limit')).toBe('50');
          expect(url.searchParams.get('cursor')).toBe('message-cursor');
          return HttpResponse.json({
            session_id: 'session-1',
            messages: [],
            next_cursor: null,
          });
        },
      ),
    );

    await api.listConversations('user-1', 'session-cursor');
    const messages = await api.listConversationMessages(
      'user-1',
      'session-1',
      'message-cursor',
    );

    expect(messages.session_id).toBe('session-1');
  });
});
