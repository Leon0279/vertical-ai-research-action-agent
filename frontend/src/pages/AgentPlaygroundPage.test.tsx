import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../test/render';
import { AgentPlaygroundPage } from './AgentPlaygroundPage';

describe('AgentPlaygroundPage', () => {
  it('blocks an empty research request before sending', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AgentPlaygroundPage />);

    await user.click(screen.getByRole('button', { name: /运行 Agent/ }));

    expect(await screen.findByText('请输入研究请求')).toBeInTheDocument();
    expect(screen.getByText('尚未运行')).toBeInTheDocument();
  });
});
