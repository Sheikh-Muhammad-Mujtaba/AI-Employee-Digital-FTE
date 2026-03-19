import Sidebar from "@/components/Sidebar";

export default function TasksLayout({ children }: { children: React.ReactNode }) {
  return <Sidebar>{children}</Sidebar>;
}
