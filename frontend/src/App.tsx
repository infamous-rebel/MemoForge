import { Routes, Route, Navigate } from "react-router-dom";
import { ToastProvider } from "./components/Toast";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import GenerateMemo from "./pages/GenerateMemo";
import MemoReview from "./pages/MemoReview";
import ECLDashboard from "./pages/ECLDashboard";
import Reports from "./pages/Reports";
import AuditLog from "./pages/AuditLog";
import Admin from "./pages/Admin";
import NotificationCenter from "./pages/NotificationCenter";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const role = localStorage.getItem("role");
  if (role !== "Admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        {/* Public */}
        <Route path="/" element={<Landing />} />
        <Route path="/landing" element={<Landing />} />
        <Route path="/login" element={<Login />} />

        {/* Protected application */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/generate" element={<GenerateMemo />} />
                  <Route path="/review/:memoId" element={<MemoReview />} />
                  <Route path="/ecl" element={<ECLDashboard />} />
                  <Route path="/reports" element={<Reports />} />
                  <Route path="/notifications" element={<NotificationCenter />} />
                  <Route path="/audit" element={<AuditLog />} />
                  <Route path="/admin" element={<AdminRoute><Admin /></AdminRoute>} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ToastProvider>
  );
}
