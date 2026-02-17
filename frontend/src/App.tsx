import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import AdminDashboard from "./pages/admin/AdminDashboard";
import SearchMailbox from "./pages/admin/SearchMailbox";
import RecordEntry from "./pages/admin/RecordEntry";
import MemberDashboard from "./pages/member/MemberDashboard";
import NotificationSettings from "./pages/member/NotificationSettings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Login />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/add" element={<SearchMailbox />} />
          <Route path="/admin/add/record/:mailboxId" element={<RecordEntry />} />
          <Route path="/member" element={<MemberDashboard />} />
          <Route path="/member/settings" element={<NotificationSettings />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
