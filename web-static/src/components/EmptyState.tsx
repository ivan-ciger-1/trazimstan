type EmptyStateProps = {
  onReset: () => void;
};

function EmptyState({ onReset }: EmptyStateProps) {
  return (
    <div className="rounded-2xl border border-white/5 bg-white/5 p-6 text-slate-200 shadow-lg">
      <div className="flex items-start gap-3">
        <div className="mt-1 h-8 w-8 rounded-full bg-purple-500/20 text-purple-100 flex items-center justify-center font-semibold">
          !
        </div>
        <div className="space-y-1">
          <h3 className="text-lg font-semibold">No listings found</h3>
          <p className="text-sm text-slate-400">
            Adjust filters or reset to see more results.
          </p>
          <div className="flex gap-2 pt-2">
            <button type="button" className="btn-primary" onClick={onReset}>
              Reset filters
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EmptyState;

