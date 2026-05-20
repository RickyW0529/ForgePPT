import UploadNode from './UploadNode';
import AgentNode from './AgentNode';
import PageAllocatorNode from './PageAllocatorNode';
import MergeNode from './MergeNode';
import ExportNode from './ExportNode';

export const nodeTypes = {
  upload: UploadNode,
  agent: AgentNode,
  page_allocator: PageAllocatorNode,
  merge: MergeNode,
  export: ExportNode,
};
