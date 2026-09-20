import { HttpResponse, http } from 'msw';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { server } from '../test/server';
import { renderWithProviders } from '../test/render';
import { MemoryPage } from './MemoryPage';

describe('MemoryPage', () => {
  it('appends the next cursor page instead of replacing existing records', async () => {
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
      http.get('http://localhost/api/v1/memories/summary', () =>
        HttpResponse.json({
          project_id: 'project-1',
          project_profile: { count: 1, last_updated_at: null },
          decisions: { count: 2, last_updated_at: null },
          actions: { count: 0, last_updated_at: null },
          policies: { count: 0, last_updated_at: null },
          research_knowledge: { count: 0, last_updated_at: null },
        }),
      ),
      http.get('http://localhost/api/v1/memories/decisions', ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor');
        return HttpResponse.json({
          project_id: 'project-1',
          items: [
            {
              decision_id: cursor ? 'decision-2' : 'decision-1',
              decision_title: cursor ? '第二个决策' : '第一个决策',
              alternatives: [],
              tradeoffs: [],
              source_refs: [],
            },
          ],
          next_cursor: cursor ? null : 'cursor-2',
        });
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<MemoryPage />);
    await user.click(screen.getByRole('tab', { name: 'Decisions' }));

    expect(await screen.findByText('第一个决策')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '加载下一页' }));
    expect(await screen.findByText('第二个决策')).toBeInTheDocument();
    expect(screen.getByText('第一个决策')).toBeInTheDocument();
    expect(screen.getByText('已加载全部 2 条记录')).toBeInTheDocument();
  });
});
