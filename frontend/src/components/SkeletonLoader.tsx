import React from 'react';

interface SkeletonProps {
  type?: 'card' | 'text' | 'chat' | 'table';
  count?: number;
}

export const SkeletonLoader: React.FC<SkeletonProps> = ({ type = 'card', count = 1 }) => {
  const items = Array.from({ length: count });

  if (type === 'chat') {
    return (
      <div className="flex flex-col gap-4 w-full animate-pulse">
        {items.map((_, i) => (
          <div key={i} className={`flex flex-col gap-2 ${i % 2 === 0 ? 'items-end' : 'items-start'}`}>
            <div className="h-3 w-24 bg-surface-container-high rounded" />
            <div className="h-16 w-3/4 max-w-lg bg-surface-container rounded-xl" />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'table') {
    return (
      <div className="flex flex-col divide-y divide-surface-variant/30 animate-pulse">
        {items.map((_, i) => (
          <div key={i} className="p-3.5 flex items-center justify-between gap-4">
            <div className="h-4 w-20 bg-surface-container rounded" />
            <div className="h-4 w-32 bg-surface-container-high rounded" />
            <div className="h-4 w-48 bg-surface-container rounded" />
            <div className="h-4 w-16 bg-surface-container-high rounded" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full animate-pulse">
      {items.map((_, i) => (
        <div key={i} className="p-4 bg-surface-container-low rounded-xl border border-surface-variant/30 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="h-5 w-32 bg-surface-container-high rounded" />
            <div className="h-5 w-10 bg-surface-container rounded-full" />
          </div>
          <div className="h-3 w-full bg-surface-container rounded" />
          <div className="h-3 w-2/3 bg-surface-container rounded" />
          <div className="flex items-center justify-between pt-2 border-t border-surface-variant/20">
            <div className="h-4 w-16 bg-surface-container rounded" />
            <div className="h-4 w-24 bg-surface-container rounded" />
          </div>
        </div>
      ))}
    </div>
  );
};
