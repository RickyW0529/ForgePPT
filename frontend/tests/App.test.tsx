import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../src/App';

describe('App', () => {
  it('renders three nodes', () => {
    render(<App />);
    expect(screen.getByText('上传解析')).toBeInTheDocument();
    expect(screen.getByText('编辑')).toBeInTheDocument();
    expect(screen.getByText('导出 PPTX')).toBeInTheDocument();
  });
});

describe('Sidebar', () => {
  it('opens when a node is clicked', () => {
    render(<App />);
    const editorNode = screen.getByText('编辑');
    fireEvent.click(editorNode);
    expect(screen.getByText('参数配置')).toBeInTheDocument();
  });
});
