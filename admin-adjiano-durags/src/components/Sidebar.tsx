"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ShoppingBag, Package, Tag, Users, Percent, Mail, Image, LogOut } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { useRouter } from "next/navigation";

const allLinks = [
  { href: "/dashboard",       label: "Dashboard",      icon: LayoutDashboard, adminOnly: false },
  { href: "/orders",          label: "Orders",         icon: ShoppingBag,     adminOnly: false },
  { href: "/products",        label: "Products",       icon: Package,         adminOnly: true  },
  { href: "/categories",      label: "Categories",     icon: Tag,             adminOnly: true  },
  { href: "/editorials",      label: "Editorials",     icon: Image,           adminOnly: true  },
  { href: "/customers",       label: "Customers",      icon: Users,           adminOnly: true  },
  { href: "/discount-codes",  label: "Discount Codes", icon: Percent,         adminOnly: true  },
  { href: "/marketing",       label: "Marketing",      icon: Mail,            adminOnly: true  },
];

export default function Sidebar({ role, email }: { role: "admin" | "staff"; email: string }) {
  const pathname = usePathname();
  const router   = useRouter();
  const links    = role === "admin" ? allLinks : allLinks.filter((l) => !l.adminOnly);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.push("/login");
  };

  return (
    <aside style={{ width: "220px", minHeight: "100vh", backgroundColor: "#000", display: "flex", flexDirection: "column", flexShrink: 0 }}>
      {/* Logo */}
      <div style={{ padding: "2rem 1.5rem 1.5rem", borderBottom: "1px solid #222" }}>
        <p style={{ fontFamily: "var(--font-montserrat)", fontSize: "11px", fontWeight: 600, letterSpacing: "0.3em", textTransform: "uppercase", color: "#fff" }}>ADJIANO</p>
        <p style={{ fontFamily: "var(--font-montserrat)", fontSize: "9px", letterSpacing: "0.2em", textTransform: "uppercase", color: "#555", marginTop: "3px" }}>Admin</p>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "1rem 0" }}>
        {links.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link key={href} href={href} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.75rem 1.5rem", backgroundColor: active ? "#111" : "transparent", borderLeft: active ? "2px solid #fff" : "2px solid transparent", color: active ? "#fff" : "#666", transition: "all 0.15s" }}>
              <Icon size={15} strokeWidth={1.5} />
              <span style={{ fontFamily: "var(--font-montserrat)", fontSize: "10px", letterSpacing: "0.15em", textTransform: "uppercase" }}>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User + sign out */}
      <div style={{ padding: "1rem 1.5rem", borderTop: "1px solid #222" }}>
        <p style={{ fontFamily: "var(--font-montserrat)", fontSize: "9px", color: "#555", letterSpacing: "0.08em", marginBottom: "0.75rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{email}</p>
        <button onClick={handleSignOut} style={{ display: "flex", alignItems: "center", gap: "0.5rem", background: "none", border: "none", cursor: "pointer", color: "#555", padding: 0 }}>
          <LogOut size={13} strokeWidth={1.5} />
          <span style={{ fontFamily: "var(--font-montserrat)", fontSize: "9px", letterSpacing: "0.15em", textTransform: "uppercase" }}>Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
