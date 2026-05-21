import { render, screen } from '@testing-library/react';
import { describe, expect, it, beforeEach } from 'vitest';
import ParamPanel from '../src/components/ParamPanel';
import { useWorkflowStore } from '../src/stores/useWorkflowStore';

beforeEach(() => {
  useWorkflowStore.getState().reset();
});

describe('ParamPanel', () => {
  it('shows the agent role as a compact chip instead of a role selector', () => {
    useWorkflowStore.getState().setNodes([
      {
        id: 'agent-1',
        type: 'agent',
        position: { x: 0, y: 0 },
        data: {
          status: 'idle',
          role: 'text_refiner',
          prompt: '',
          temperature: 0.3,
          pageScope: [],
        },
      },
    ]);

    render(<ParamPanel nodeId="agent-1" />);

    expect(screen.getByText('文本润色')).toBeInTheDocument();
    expect(screen.queryByText('文本润色 Agent')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('角色')).not.toBeInTheDocument();
  });

  it('uses compact field labels without helper copy', () => {
    useWorkflowStore.getState().setNodes([
      {
        id: 'agent-2',
        type: 'agent',
        position: { x: 0, y: 0 },
        data: {
          status: 'idle',
          role: 'theme_designer',
          prompt: '',
          temperature: 0.3,
          pageScope: [],
        },
      },
    ]);

    render(<ParamPanel nodeId="agent-2" />);

    expect(screen.getByText('Prompt')).toBeInTheDocument();
    expect(screen.getByText('页面范围')).toBeInTheDocument();
    expect(screen.queryByText('告诉这个 Agent 要如何处理 PPT 内容')).not.toBeInTheDocument();
    expect(screen.queryByText('留空表示处理全部页面，例如：1, 3, 5')).not.toBeInTheDocument();
  });
});
