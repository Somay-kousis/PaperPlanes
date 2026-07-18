import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router";

import "./index.css";
import App from "./App.jsx";
import ChatPage from "./pages/ChatPage.jsx";
import LibraryPage from "./pages/LibraryPage.jsx";
import MemoryInspectorPage from "./pages/MemoryInspectorPage.jsx";
import ContradictionsPage from "./pages/ContradictionsPage.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="chat/:sessionId" element={<ChatPage />} />
          <Route path="library" element={<LibraryPage />} />
          <Route path="memory" element={<MemoryInspectorPage />} />
          <Route path="contradictions" element={<ContradictionsPage />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
