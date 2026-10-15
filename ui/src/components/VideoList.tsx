import type { Video } from "../api";
import { StateBadge } from "./StateBadge";

interface Props {
  videos: Video[];
  selected: string | null;
  onSelect(id: string): void;
}

export function VideoList({ videos, selected, onSelect }: Props) {
  if (!videos.length) return <p className="av-muted">Aucune vidéo pour l'instant.</p>;
  return (
    <ul className="av-list">
      {videos.map((v) => (
        <li key={v.id}>
          <button className={v.id === selected ? "av-item av-selected" : "av-item"} onClick={() => onSelect(v.id)}>
            <span className="av-item-name">{v.name}</span>
            <StateBadge state={v.state} step={v.step} />
          </button>
        </li>
      ))}
    </ul>
  );
}
