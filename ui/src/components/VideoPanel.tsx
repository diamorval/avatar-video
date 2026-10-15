import {
  Alert,
  Panel,
  PanelContent,
  PanelHeader,
  PanelTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  type TagTone,
} from "@diametral/design-system/react";
import type { Step, VideoDetail } from "../api";
import { STEP_LABELS, StateBadge } from "./StateBadge";

const STEPS = Object.keys(STEP_LABELS) as Step[];
const STEP_TONES: Record<string, TagTone> = { done: "success", running: "warning", error: "danger", todo: "neutral" };

interface Props {
  video: VideoDetail;
  finalUrl: string;
}

export function VideoPanel({ video, finalUrl }: Props) {
  const current = video.step ? STEPS.indexOf(video.step) : -1;
  function stepState(i: number) {
    if (video.state === "done") return "done";
    if (i < current) return "done";
    if (i === current) return video.state === "error" ? "error" : "running";
    return "todo";
  }

  return (
    <Panel>
      <PanelHeader className="av-panel-head">
        <PanelTitle role="heading" aria-level={2}>
          {video.name}
        </PanelTitle>
        <StateBadge state={video.state} step={video.step} />
      </PanelHeader>
      <PanelContent>
        <ol className="av-steps">
          {STEPS.map((s, i) => (
            <li key={s}>
              <Tag tone={STEP_TONES[stepState(i)]} className={`av-step av-step-${stepState(i)}`}>
                {STEP_LABELS[s]}
              </Tag>
            </li>
          ))}
        </ol>
        {video.error && <Alert tone="danger" className="av-alert">{video.error}</Alert>}
        {video.final && (
          <div className="av-player">
            <video src={finalUrl} controls />
            <a href={finalUrl} download={`${video.id}.mp4`}>
              Télécharger le MP4
            </a>
          </div>
        )}
        {video.segments.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Phrase</TableHead>
                <TableHead>Geste</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {video.segments.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>{s.id}</TableCell>
                  <TableCell>{s.text}</TableCell>
                  <TableCell>{s.clip ?? s.driver ?? s.prompt}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </PanelContent>
    </Panel>
  );
}
