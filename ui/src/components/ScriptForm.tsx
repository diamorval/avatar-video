import { useState, type FormEvent } from "react";
import {
  Alert,
  Button,
  buttonVariants,
  Field,
  FieldLabel,
  Input,
  Panel,
  PanelContent,
  PanelHeader,
  PanelTitle,
  Textarea,
} from "@diametral/design-system/react";
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
    <Panel>
      <PanelHeader>
        <PanelTitle>Nouvelle vidéo</PanelTitle>
      </PanelHeader>
      <PanelContent>
        <form className="av-form" onSubmit={submit}>
          <Field>
            <FieldLabel htmlFor="av-name">Nom</FieldLabel>
            <Input id="av-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Présentation produit" required />
          </Field>
          <Field
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files[0];
              if (file) void loadFile(file);
            }}
          >
            <FieldLabel htmlFor="av-script">Script</FieldLabel>
            <Textarea
              id="av-script"
              value={script}
              onChange={(e) => setScript(e.target.value)}
              placeholder="Colle le script ou dépose un fichier .txt ici"
              rows={8}
              required
            />
          </Field>
          <div className="av-row">
            <label className={`av-file ${buttonVariants({ variant: "outline" })}`}>
              <input type="file" accept=".txt,text/plain" onChange={(e) => e.target.files?.[0] && void loadFile(e.target.files[0])} />
              Choisir un .txt
            </label>
            <span className="ds-select ds-select--block">
              <select value={backend} onChange={(e) => setBackend(e.target.value as Backend)} aria-label="Backend">
                <option value="mac">Mac : gestes de la source</option>
                <option value="gpu">GPU : gestes générés</option>
              </select>
            </span>
            <Button type="submit" variant="primary" disabled={busy || !name.trim() || !script.trim()}>
              {busy ? "Envoi…" : "Générer"}
            </Button>
          </div>
          {error && <Alert tone="danger">{error}</Alert>}
        </form>
      </PanelContent>
    </Panel>
  );
}
