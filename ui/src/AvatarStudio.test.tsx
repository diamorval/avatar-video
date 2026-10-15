import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { AvatarStudio } from "./AvatarStudio";
import type { Api, VideoDetail } from "./api";

afterEach(cleanup);

function fakeApi(videos: VideoDetail[]): Api {
  return {
    info: vi.fn(async () => ({ default_backend: "mac" as const, source_ready: true, clips: [], drivers: [] })),
    list: vi.fn(async () => videos),
    get: vi.fn(async (id: string) => videos.find((v) => v.id === id)!),
    create: vi.fn(async (body) => {
      const v: VideoDetail = {
        id: "regles", name: body.name, backend: body.backend ?? "mac", state: "queued", step: null,
        error: null, created: 2, updated: 2, segments: [], final: null,
      };
      videos.unshift(v);
      return v;
    }),
    finalUrl: (id) => `/api/videos/${id}/final.mp4`,
  };
}

const DONE: VideoDetail = {
  id: "intro", name: "Intro", backend: "mac", state: "done", step: null, error: null, created: 1,
  updated: 1, final: "/work/intro/final.mp4",
  segments: [{ id: 1, text: "Bienvenue dans le jeu.", clip: "explique" }],
};

test("affiche la dernière vidéo avec son lecteur et ses segments", async () => {
  render(<AvatarStudio api={fakeApi([DONE])} />);
  expect(await screen.findByText("Bienvenue dans le jeu.")).toBeTruthy();
  expect(screen.getByText("explique")).toBeTruthy();
  expect(screen.getByText("Télécharger le MP4").getAttribute("href")).toBe("/api/videos/intro/final.mp4");
});

test("envoie le script et sélectionne la nouvelle vidéo", async () => {
  const api = fakeApi([DONE]);
  render(<AvatarStudio api={api} />);
  await screen.findByText("Bienvenue dans le jeu.");

  fireEvent.change(screen.getByPlaceholderText("Règles du jeu"), { target: { value: "Règles" } });
  fireEvent.change(screen.getByPlaceholderText(/Colle le script/), { target: { value: "Trois règles." } });
  await act(async () => fireEvent.click(screen.getByText("Générer")));

  expect(api.create).toHaveBeenCalledWith({ name: "Règles", script: "Trois règles.", backend: "mac" });
  await waitFor(() => expect(screen.getByRole("heading", { name: "Règles" })).toBeTruthy());
  expect(screen.getAllByText("En attente").length).toBeGreaterThan(0);
});

test("montre l'étape en erreur et son message", async () => {
  const failed: VideoDetail = { ...DONE, state: "error", step: "voice", error: "ModuleNotFoundError: chatterbox", final: null };
  render(<AvatarStudio api={fakeApi([failed])} />);
  expect(await screen.findByText("ModuleNotFoundError: chatterbox")).toBeTruthy();
  expect(document.querySelector(".av-step-error")?.textContent).toBe("Voix");
});
