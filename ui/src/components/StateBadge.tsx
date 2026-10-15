import type { State, Step } from "../api";

export const STEP_LABELS: Record<Step, string> = {
  segment: "Découpage",
  voice: "Voix",
  video: "Vidéo",
  assemble: "Assemblage",
};

const STATE_LABELS: Record<State, string> = {
  queued: "En attente",
  running: "En cours",
  done: "Terminée",
  error: "Erreur",
};

export function StateBadge({ state, step }: { state: State; step: Step | null }) {
  const label = state === "running" && step ? STEP_LABELS[step] : STATE_LABELS[state];
  return <span className={`av-badge av-${state}`}>{label}</span>;
}
