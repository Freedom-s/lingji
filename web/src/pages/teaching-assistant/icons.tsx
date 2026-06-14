/**
 * Geometric SVG icons — 44×44 filled + stroked, with color accent backgrounds.
 * 8 distinct shapes, each with its own refined muted color palette.
 */

interface IconSpec {
  bg: string;
  stroke: string;
  shape: (s: string) => React.ReactNode;
}

function Circle(c: string) {
  return <circle cx="22" cy="22" r="12" fill="none" stroke={c} strokeWidth="2" />;
}
function Square(c: string) {
  return <rect x="9" y="9" width="26" height="26" rx="6" fill="none" stroke={c} strokeWidth="2" />;
}
function Triangle(c: string) {
  return <path d="M22 8L36 34H8L22 8Z" fill="none" stroke={c} strokeWidth="2" strokeLinejoin="round" />;
}
function Hexagon(c: string) {
  return <path d="M22 6L36.5 14.5V29.5H7.5V14.5L22 6Z" fill="none" stroke={c} strokeWidth="2" strokeLinejoin="round" />;
}
function Diamond(c: string) {
  return <rect x="22" y="5" width="22" height="22" rx="3" transform="rotate(45 22 5)" fill="none" stroke={c} strokeWidth="2" />;
}
function Overlap(c: string) {
  return (
    <>
      <circle cx="15" cy="15" r="10" fill="none" stroke={c} strokeWidth="2" />
      <circle cx="29" cy="29" r="10" fill="none" stroke={c} strokeWidth="2" />
    </>
  );
}
function RoundedSquare(c: string) {
  return <rect x="7" y="7" width="30" height="30" rx="8" fill="none" stroke={c} strokeWidth="2" />;
}
function Lines(c: string) {
  return (
    <>
      <line x1="8" y1="14" x2="36" y2="14" stroke={c} strokeWidth="2" strokeLinecap="round" />
      <line x1="12" y1="22" x2="32" y2="22" stroke={c} strokeWidth="2" strokeLinecap="round" />
      <line x1="8" y1="30" x2="36" y2="30" stroke={c} strokeWidth="2" strokeLinecap="round" />
    </>
  );
}

const ICONS: IconSpec[] = [
  { bg: '#eef2ff', stroke: '#6366f1', shape: Circle },        // indigo
  { bg: '#ecfdf5', stroke: '#10b981', shape: Square },        // emerald
  { bg: '#fffbeb', stroke: '#f59e0b', shape: Triangle },      // amber
  { bg: '#fff1f2', stroke: '#e11d48', shape: Hexagon },       // rose
  { bg: '#ecfeff', stroke: '#06b6d4', shape: Diamond },       // cyan
  { bg: '#f5f3ff', stroke: '#8b5cf6', shape: Overlap },       // violet
  { bg: '#f0fdfa', stroke: '#14b8a6', shape: RoundedSquare }, // teal (larger rect)
  { bg: '#f0f9ff', stroke: '#0ea5e9', shape: Lines },         // sky
];

export function getIconSvg(index: number): React.ReactNode {
  const spec = ICONS[index % ICONS.length];
  return (
    <div
      style={{
        width: 56,
        height: 56,
        borderRadius: 14,
        background: spec.bg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
        {spec.shape(spec.stroke)}
      </svg>
    </div>
  );
}
