import { useCallback, useEffect, useMemo, useState } from "react";
import { createApi, type Api, type SourceInfo, type Video, type VideoDetail } from "./api";
import { ScriptForm } from "./components/ScriptForm";
import { VideoList } from "./components/VideoList";
import { VideoPanel } from "./components/VideoPanel";

export interface AvatarStudioProps {
  /** URL du serveur `avatar serve`. Vide quand l'UI est servie par lui. */
  apiBase?: string;
  /** Client déjà construit, à la place de apiBase (tests, auth maison). */
  api?: Api;
  /** Intervalle de rafraîchissement pendant une génération, en ms. */
  pollMs?: number;
}

/** L'app complète : envoi de script, suivi des vidéos, lecture du résultat. */
export function AvatarStudio({ apiBase = "", api: given, pollMs = 2000 }: AvatarStudioProps) {
  const api = useMemo(() => given ?? createApi(apiBase), [given, apiBase]);
  const [info, setInfo] = useState<SourceInfo | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<VideoDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    async (want: string | null = selected) => {
      try {
        const list = await api.list();
        setVideos(list);
        const id = want ?? list[0]?.id ?? null;
        if (id !== selected) setSelected(id);
        setDetail(id ? await api.get(id) : null);
        setError(null);
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [api, selected],
  );

  useEffect(() => {
    api.info().then(setInfo, (err: Error) => setError(err.message));
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Rafraîchit tant qu'une vidéo est en file ou en cours, y compris celles lancées par Claude via MCP.
  const busy = videos.some((v) => v.state === "queued" || v.state === "running");
  useEffect(() => {
    const timer = setInterval(() => void refresh(), busy ? pollMs : pollMs * 5);
    return () => clearInterval(timer);
  }, [busy, pollMs, refresh]);

  return (
    <div className="av-studio">
      <header className="av-top">
        <h1>Avatar vidéo</h1>
        {info && !info.source_ready && (
          <p className="av-warn">Source non préparée : lance `avatar prepare` avant de générer.</p>
        )}
      </header>
      {error && <p className="av-error">{error}</p>}
      <div className="av-layout">
        <aside>
          <ScriptForm
            defaultBackend={info?.default_backend ?? "mac"}
            onSubmit={async (body) => {
              const video = await api.create(body);
              await refresh(video.id);
            }}
          />
          <h2 className="av-section">Vidéos</h2>
          <VideoList videos={videos} selected={selected} onSelect={setSelected} />
        </aside>
        <main>
          {detail ? (
            <VideoPanel video={detail} finalUrl={api.finalUrl(detail.id)} />
          ) : (
            <p className="av-muted">Envoie un script pour créer ta première vidéo.</p>
          )}
        </main>
      </div>
    </div>
  );
}
