import { Outlet } from "react-router";
import Sidebar from "./components/Sidebar.jsx";
import InteractiveBackground from "./components/InteractiveBackground.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <InteractiveBackground />
      <Sidebar />
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
