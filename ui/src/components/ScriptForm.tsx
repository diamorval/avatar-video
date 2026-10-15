import { useState, type FormEvent } from "react";
import type { Backend } from "../api";

interface Props {
  defaultBackend: Backend;
  onSubmit(body: { name: string; script: string; backend: Backend }): Promise<void>;
}

/** Envoi d'un script (.txt ou texte collé) : tout le reste est automatique. */
export function ScriptForm({ defaultBackend, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [script, setScript] = useState("");
  const [backend, setBackend] = useState<Backend>(defaultBackend);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadFile(file: File) {
    setScript(await file.text());
    if (!name) setName(file.name.replace(/\.txt$/i, ""));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ name: name.trim(), script, backend });
      setName("");
      setScript("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="av-card av-form" onSubmit={submit}>
      <h2>Nouvelle vidéo</h2>
      <label>
        Nom
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Règles du jeu" required />
      </label>
      <label
        className="av-drop"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files[0];
          if (file) void loadFile(file);
        }}
      >
        Script
        <textarea
          value={script}
          onChange={(e) => setScript(e.target.value)}
          placeholder="Colle le script ou dépose un fichier .txt ici"
          rows={8}
          required
        />
      </label>
      <div className="av-row">
        <label className="av-file">
          <input type="file" accept=".txt,text/plain" onChange={(e) => e.target.files?.[0] && void loadFile(e.target.files[0])} />
          Choisir un .txt
        </label>
        <select value={backend} onChange={(e) => setBackend(e.target.value as Backend)} aria-label="Backend">
          <option value="mac">Mac : gestes de la source</option>
          <option value="gpu">GPU : gestes générés</option>
        </select>
        <button type="submit" disabled={busy || !name.trim() || !script.trim()}>
          {busy ? "Envoi…" : "Générer"}
        </button>
      </div>
      {error && <p className="av-error">{error}</p>}
    </form>
  );
}
