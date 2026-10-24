/** doctool mark: five colored folder tabs, one per tool group. Decorative; the wordmark carries the name. */
export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  const tabs = [
    ["var(--organize)", 6, 12],
    ["var(--optimize)", 11, 8],
    ["var(--convert)", 16, 14],
    ["var(--edit)", 21, 10],
    ["var(--security)", 26, 16],
  ] as const;
  return (
    <svg aria-hidden viewBox="0 0 36 36" className={className}>
      <rect width="36" height="36" rx="9" fill="var(--text)" />
      {tabs.map(([fill, x, h]) => (
        <rect key={x} x={x - 2} y={30 - h - 2} width="4" height={h} rx="1.5" fill={fill} />
      ))}
    </svg>
  );
}
