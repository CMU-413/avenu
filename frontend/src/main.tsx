import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.tsx";
import "./index.css";

const rawBasePath = import.meta.env.VITE_BASE_PATH || "/mail/";
const normalizedBasePath = rawBasePath.endsWith("/") ? rawBasePath.slice(0, -1) : rawBasePath;

createRoot(document.getElementById("root")!).render(
  <BrowserRouter basename={normalizedBasePath}>
    <App />
  </BrowserRouter>
);
