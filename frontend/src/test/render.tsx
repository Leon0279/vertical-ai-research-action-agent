import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App as AntApp, ConfigProvider } from 'antd';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';

import { WorkspaceProvider } from '../state/workspace';

export function renderWithProviders(
  ui: ReactElement,
  options: { initialEntries?: string[] } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <ConfigProvider>
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <WorkspaceProvider>
            <MemoryRouter initialEntries={options.initialEntries}>{ui}</MemoryRouter>
          </WorkspaceProvider>
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>,
  );
}
