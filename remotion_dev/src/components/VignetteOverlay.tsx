// VignetteOverlay was a global radial-gradient that darkened the canvas
// edges. The no-gradient rule (locked 2026-05-13) kills it — vignettes are
// atmospheric in a way that conflicts with the flat, solid, confident look
// we're going for. Keeping the file as a no-op so existing imports don't
// break, but it intentionally renders nothing.
export const VignetteOverlay: React.FC = () => null;
