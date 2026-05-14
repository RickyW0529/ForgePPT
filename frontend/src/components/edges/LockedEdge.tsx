import { memo } from 'react';
import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@xyflow/react';

const LockedEdge = memo(({ sourceX, sourceY, targetX, targetY }: EdgeProps) => {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  return (
    <BaseEdge
      path={edgePath}
      style={{ stroke: '#2E4A62', strokeWidth: 2 }}
    />
  );
});

export default LockedEdge;
