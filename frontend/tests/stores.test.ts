import { describe, it, expect } from 'vitest';
import { useTaskStore } from '../src/stores/useTaskStore';
import { useUIStore } from '../src/stores/useUIStore';

describe('useTaskStore', () => {
  it('should initialize with idle status', () => {
    const state = useTaskStore.getState();
    expect(state.overallStatus).toBe('idle');
    expect(state.nodeStatuses).toEqual({});
  });

  it('should update node status', () => {
    useTaskStore.getState().setNodeStatus('editor', 'processing');
    expect(useTaskStore.getState().nodeStatuses['editor']).toBe('processing');
  });
});

describe('useUIStore', () => {
  it('should toggle sidebar', () => {
    const { toggleSidebar } = useUIStore.getState();
    toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(false);
  });
});
