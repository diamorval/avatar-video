import { Tag, type TagTone } from "@diametral/design-system/react";
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

export const STATE_TONES: Record<State, TagTone> = {
  queued: "neutral",
  running: "warning",
  done: "success",
  error: "danger",
};

export function StateBadge({ state, step }: { state: State; step: Step | null }) {
  const label = state === "running" && step ? STEP_LABELS[step] : STATE_LABELS[state];
  return <Tag tone={STATE_TONES[state]}>{label}</Tag>;
}
