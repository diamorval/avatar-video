import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AvatarStudio } from "./AvatarStudio";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AvatarStudio />
  </StrictMode>,
);
