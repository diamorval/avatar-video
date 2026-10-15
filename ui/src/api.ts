export type Backend = "mac" | "gpu";
export type State = "queued" | "running" | "done" | "error";
export type Step = "segment" | "voice" | "video" | "assemble";

export interface Segment {
  id: number;
  text: string;
  clip?: string;
  driver?: string;
  prompt?: string;
}

export interface Video {
  id: string;
  name: string;
  backend: Backend;
  state: State;
  step: Step | null;
  error: string | null;
  created: number;
  updated: number;
}

export interface VideoDetail extends Video {
  segments: Segment[];
  final: string | null;
}

export interface SourceInfo {
  default_backend: Backend;
  source_ready: boolean;
  clips: string[];
  drivers: string[];
}

export interface Api {
  info(): Promise<SourceInfo>;
  list(): Promise<Video[]>;
  get(id: string): Promise<VideoDetail>;
  create(body: { name: string; script: string; backend?: Backend }): Promise<Video>;
  finalUrl(id: string): string;
}

/** Client de l'API REST d'avatar-video. `base` vaut "" quand l'UI est servie par `avatar serve`. */
export function createApi(base = ""): Api {
  async function call<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${base}/api${path}`, init);
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  }
  return {
    info: () => call("/info"),
    list: () => call("/videos"),
    get: (id) => call(`/videos/${encodeURIComponent(id)}`),
    create: (body) =>
      call("/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    finalUrl: (id) => `${base}/api/videos/${encodeURIComponent(id)}/final.mp4`,
  };
}
