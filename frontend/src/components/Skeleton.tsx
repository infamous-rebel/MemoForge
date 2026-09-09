/** Loading skeletons for async surfaces. */

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div
      className={`relative overflow-hidden rounded-lg bg-frost-mist/70 ${className}`}
      aria-hidden="true"
    >
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/60 to-transparent" />
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="card p-6">
      <SkeletonBlock className="mb-4 h-3 w-24" />
      <SkeletonBlock className="mb-2 h-8 w-32" />
      <SkeletonBlock className="h-3 w-20" />
    </div>
  );
}

export function SkeletonTable({ rows = 4, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="card overflow-hidden" aria-busy="true">
      <div className="table-head grid gap-4 px-6 py-3" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonBlock key={i} className="h-2.5 w-3/4" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="table-row grid gap-4 px-6 py-4"
          style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
        >
          {Array.from({ length: cols }).map((_, c) => (
            <SkeletonBlock key={c} className="h-3.5 w-full" />
          ))}
        </div>
      ))}
    </div>
  );
}
