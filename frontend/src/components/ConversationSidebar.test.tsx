import { HttpResponse, http } from 'msw';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { server } from '../test/server';
import { renderWithProviders } from '../test/render';
import { ConversationSidebar } from './ConversationSidebar';

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="location">{location.pathname}</output>;
}

const session = (
  id: string,
  title: string,
  projectId: string | null,
  status: 'active' | 'archived' = 'active',
) => ({
  session_id: id,
  project_id: projectId,
  title,
  session_status: status,
  created_at: '2026-09-20T08:00:00Z',
  updated_at: '2026-09-20T09:00:00Z',
  last_message_at: '2026-09-20T09:00:00Z',
});

describe('ConversationSidebar', () => {
  it('loads paginated sessions, resolves project names, and selects a session', async () => {
    server.use(
      http.get('http://localhost/api/v1/conversations', ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor');
        return HttpResponse.json(
          cursor
            ? {
                sessions: [
                  session('session-older', '更早的讨论', 'project-missing', 'archived'),
                ],
                next_cursor: null,
              }
            : {
                sessions: [
                  session('session-1', 'Research history', 'project-1'),
                  session('session-2', '没有项目的讨论', null),
                ],
                next_cursor: 'next-page',
              },
        );
      }),
      http.get('http://localhost/api/v1/projects/project-1', () =>
        HttpResponse.json({
          project_id: 'project-1',
          project_name: 'Acme 研究',
        }),
      ),
      http.get('http://localhost/api/v1/projects/project-missing', () =>
        HttpResponse.json(
          { error_code: 'PROJECT_NOT_FOUND', error_reason: '不存在' },
          { status: 404 },
        ),
      ),
    );

    const user = userEvent.setup();
    renderWithProviders(
      <>
        <ConversationSidebar collapsed={false} />
        <LocationProbe />
      </>,
    );

    expect(await screen.findByText('Research history')).toBeInTheDocument();
    expect(await screen.findByText('Acme 研究 · project-1')).toBeInTheDocument();
    expect(screen.getByText('无项目')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '加载更多' }));
    expect(await screen.findByText('更早的讨论')).toBeInTheDocument();
    expect(screen.getByText('project-missing')).toBeInTheDocument();
    expect(screen.getByText('已归档')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Research history/ }));
    expect(screen.getByLabelText('location')).toHaveTextContent('/agent/session-1');
    const stored = JSON.parse(
      localStorage.getItem('vaa.debug.workspace.v1') ?? '{}',
    );
    expect(stored).toMatchObject({
      userId: 'local-demo',
      projectId: 'project-1',
      sessionId: 'session-1',
    });
  });

  it('switches the global user and clears the previous project and session', async () => {
    localStorage.setItem(
      'vaa.debug.workspace.v1',
      JSON.stringify({
        userId: 'user-1',
        projectId: 'project-1',
        sessionId: 'old-session',
        iterationBudget: 2,
      }),
    );
    server.use(
      http.get('http://localhost/api/v1/conversations', () =>
        HttpResponse.json({ sessions: [], next_cursor: null }),
      ),
    );

    const user = userEvent.setup();
    renderWithProviders(
      <>
        <ConversationSidebar collapsed={false} />
        <LocationProbe />
      </>,
      { initialEntries: ['/projects'] },
    );

    const input = screen.getByLabelText('全局 User ID');
    await user.clear(input);
    await user.type(input, 'user-2');
    await user.click(screen.getByRole('button', { name: /选\s*择/ }));

    expect(screen.getByLabelText('location')).toHaveTextContent('/agent');
    const stored = JSON.parse(
      localStorage.getItem('vaa.debug.workspace.v1') ?? '{}',
    );
    expect(stored.userId).toBe('user-2');
    expect(stored.projectId).toBe('');
    expect(stored.sessionId).not.toBe('old-session');
  });
});
