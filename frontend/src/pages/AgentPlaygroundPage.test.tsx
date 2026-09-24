import { HttpResponse, http } from 'msw';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { server } from '../test/server';
import { renderWithProviders } from '../test/render';
import { AgentPlaygroundPage } from './AgentPlaygroundPage';

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="location">{location.pathname}</output>;
}

describe('AgentPlaygroundPage', () => {
  it('blocks an empty research request before sending', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AgentPlaygroundPage />);

    await user.click(screen.getByRole('button', { name: /运行 Agent/ }));

    expect(await screen.findByText('请输入研究请求')).toBeInTheDocument();
    expect(screen.getByText('尚未运行')).toBeInTheDocument();
  });

  it('opens the persisted conversation and refreshes its history after a successful run', async () => {
    localStorage.setItem(
      'vaa.debug.workspace.v1',
      JSON.stringify({
        userId: 'user-1',
        projectId: 'project-1',
        sessionId: 'session-1',
        iterationBudget: 2,
      }),
    );
    server.use(
      http.post('http://localhost/api/v1/agent/run', async ({ request }) => {
        const body = await request.json();
        expect(body).toMatchObject({
          query: '继续研究',
          user_id: 'user-1',
          project_id: 'project-1',
          session_id: 'session-1',
        });
        return HttpResponse.json({
          trace_id: 'trace-1',
          task_type: 'research',
          workflow_pattern: 'research',
          answer: '最新回答',
          summary: '已完成',
          recommendation: null,
          action_items: [],
          citations: [],
          confidence: 0.9,
          caveats: [],
          stage_history: [],
          metadata: {},
        });
      }),
      http.get(
        'http://localhost/api/v1/conversations/session-1/messages',
        () =>
          HttpResponse.json({
            session_id: 'session-1',
            messages: [
              {
                message_id: 'message-1',
                role: 'assistant',
                content: '保存后的回答',
                content_format: 'markdown',
                created_at: '2026-09-20T10:00:00Z',
              },
            ],
            next_cursor: null,
          }),
      ),
    );

    const user = userEvent.setup();
    renderWithProviders(
      <>
        <Routes>
          <Route path="/agent" element={<AgentPlaygroundPage />} />
          <Route path="/agent/:sessionId" element={<AgentPlaygroundPage />} />
        </Routes>
        <LocationProbe />
      </>,
      { initialEntries: ['/agent'] },
    );

    await user.type(screen.getByLabelText('研究请求'), '继续研究');
    await user.click(screen.getByRole('button', { name: /运行 Agent/ }));

    expect(await screen.findByText('保存后的回答')).toBeInTheDocument();
    expect(screen.getByLabelText('location')).toHaveTextContent('/agent/session-1');
    expect(screen.getByText('运行完成')).toBeInTheDocument();
  });
});
