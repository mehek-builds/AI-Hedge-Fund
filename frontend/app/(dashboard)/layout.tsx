import { NavShell } from "@/components/ui/nav-shell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <NavShell>{children}</NavShell>;
}
