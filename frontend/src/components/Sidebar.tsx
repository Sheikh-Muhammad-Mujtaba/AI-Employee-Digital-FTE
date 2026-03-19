"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/tasks", label: "Tasks", icon: "✅" },
  { href: "/projects", label: "Projects", icon: "📁" },
  { href: "/planning", label: "AI Planning", icon: "✨" },
  { href: "/accounting", label: "Accounting", icon: "💰" },
  { href: "/whatsapp", label: "WhatsApp", icon: "💬" },
];

export default function Sidebar({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Check auth
    const token = localStorage.getItem("fte_token");
    if (!token) {
      router.replace("/login");
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("fte_token");
    router.replace("/login");
  };

  if (!mounted) return null;

  return (
    <>
      <aside className="sidebar">
        <div className="sidebar-logo">⚡ Digital FTE</div>
        <nav>
          <ul className="sidebar-nav">
            {NAV_ITEMS.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={`sidebar-link ${
                    pathname.startsWith(item.href) ? "sidebar-link--active" : ""
                  }`}
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div style={{ marginTop: "auto" }}>
          <button className="btn-ghost" style={{ width: "100%" }} onClick={handleLogout}>
            🚪 Logout
          </button>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </>
  );
}
