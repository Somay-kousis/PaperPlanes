import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router";

import "./index.css";
import App from "./App.jsx";
import LandingPage from "./pages/LandingPage.jsx";
import LibraryPage from "./pages/LibraryPage.jsx";
import ChatPage from "./pages/ChatPage.jsx";
import MemoryInspectorPage from "./pages/MemoryInspectorPage.jsx";
import ContradictionsPage from "./pages/ContradictionsPage.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<LandingPage />} />
          <Route path="library" element={<LibraryPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="memory" style={{}} element={<MemoryInspectorPage />} />
          <Route path="contradictions" element={<ContradictionsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
