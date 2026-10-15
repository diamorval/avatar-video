import type { Step, VideoDetail } from "../api";
import { STEP_LABELS, StateBadge } from "./StateBadge";

const STEPS = Object.keys(STEP_LABELS) as Step[];

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
    <section className="av-card av-panel">
      <header className="av-panel-head">
        <h2>{video.name}</h2>
        <StateBadge state={video.state} step={video.step} />
      </header>
      <ol className="av-steps">
        {STEPS.map((s, i) => (
          <li key={s} className={`av-step av-step-${stepState(i)}`}>
            {STEP_LABELS[s]}
          </li>
        ))}
      </ol>
      {video.error && <p className="av-error">{video.error}</p>}
      {video.final && (
        <div className="av-player">
          <video src={finalUrl} controls />
          <a href={finalUrl} download={`${video.id}.mp4`}>
            Télécharger le MP4
          </a>
        </div>
      )}
      {video.segments.length > 0 && (
        <table className="av-segments">
          <thead>
            <tr>
              <th>#</th>
              <th>Phrase</th>
              <th>Geste</th>
            </tr>
          </thead>
          <tbody>
            {video.segments.map((s) => (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{s.text}</td>
                <td>{s.clip ?? s.driver ?? s.prompt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
