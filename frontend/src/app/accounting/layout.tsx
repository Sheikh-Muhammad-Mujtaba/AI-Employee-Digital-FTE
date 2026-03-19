import Sidebar from "@/components/Sidebar";
import type { ReactNode } from "react";

export default function Layout({ children }: { children: ReactNode }) {
  return <Sidebar>{children}</Sidebar>;
}
