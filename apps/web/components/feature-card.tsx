export function FeatureCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-black/10 p-5 dark:border-white/10">
      <h3 className="mb-1 font-semibold">{title}</h3>
      <p className="text-sm opacity-70">{children}</p>
    </div>
  );
}
