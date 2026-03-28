"use client";
import { useEffect, useState } from "react";
import { Trash2, GripVertical } from "lucide-react";
import { supabase } from "@/lib/supabase";
import AdminShell from "@/components/AdminShell";

interface Editorial {
  id: string;
  image_url: string;
  alt_text: string;
  page: "collections" | "bestsellers";
  category_id: string | null;
  position: "after_4" | "after_2";
  active: boolean;
  sort_order: number;
}

interface Category { id: string; name: string; }

const inp: React.CSSProperties = { border: "1px solid #e0e0e0", padding: "0.65rem 0.875rem", fontFamily: "var(--font-montserrat)", fontSize: "11px", color: "#000", outline: "none", backgroundColor: "#fff", width: "100%" };
const lbl: React.CSSProperties = { fontFamily: "var(--font-montserrat)", fontSize: "9px", fontWeight: 500, letterSpacing: "0.15em", textTransform: "uppercase", color: "#888", display: "block", marginBottom: "0.35rem" };

export default function EditorialsPage() {
  const [editorials, setEditorials] = useState<Editorial[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading]       = useState(true);
  const [saving, setSaving]         = useState(false);
  const [error, setError]           = useState("");
  const [form, setForm] = useState({
    image_url:   "",
    alt_text:    "",
    page:        "collections" as "collections" | "bestsellers",
    category_id: "",
    position:    "after_4" as "after_4" | "after_2",
  });

  const load = async () => {
    const [{ data: eds }, { data: cats }] = await Promise.all([
      supabase.from("editorials").select("*").order("sort_order"),
      supabase.from("categories").select("id, name").order("name"),
    ]);
    setEditorials((eds ?? []) as Editorial[]);
    setCategories((cats ?? []) as Category[]);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setSaving(true);
    const maxOrder = editorials.length > 0 ? Math.max(...editorials.map((x) => x.sort_order)) + 1 : 0;
    const { error: err } = await supabase.from("editorials").insert({
      image_url:   form.image_url.trim(),
      alt_text:    form.alt_text.trim(),
      page:        form.page,
      category_id: form.category_id || null,
      position:    form.position,
      active:      true,
      sort_order:  maxOrder,
    });
    if (err) { setError(err.message); setSaving(false); return; }
    setForm({ image_url: "", alt_text: "", page: "collections", category_id: "", position: "after_4" });
    setSaving(false);
    load();
  };

  const toggleActive = async (id: string, current: boolean) => {
    await supabase.from("editorials").update({ active: !current }).eq("id", id);
    setEditorials((prev) => prev.map((e) => e.id === id ? { ...e, active: !current } : e));
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this editorial image?")) return;
    await supabase.from("editorials").delete().eq("id", id);
    setEditorials((prev) => prev.filter((e) => e.id !== id));
  };

  const positionLabel = (p: string) => p === "after_4" ? "After row of 4" : "After 2 stacked";

  return (
    <AdminShell>
      <h1 style={{ fontFamily: "var(--font-inria)", fontSize: "2rem", fontWeight: 400, marginBottom: "2rem" }}>Editorial Images</h1>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: "1.5rem", alignItems: "start" }}>

        {/* Create */}
        <div style={{ backgroundColor: "#fff", border: "1px solid #e5e5e5", padding: "1.5rem" }}>
          <p style={{ fontFamily: "var(--font-montserrat)", fontSize: "9px", fontWeight: 600, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: "1.25rem" }}>Add Editorial Image</p>
          <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: "0.875rem" }}>
            <div>
              <label style={lbl}>Image URL (from Cloudinary)</label>
              <input required value={form.image_url} onChange={(e) => setForm((f) => ({ ...f, image_url: e.target.value }))} placeholder="https://res.cloudinary.com/..." style={inp} />
            </div>
            <div>
              <label style={lbl}>Alt Text</label>
              <input value={form.alt_text} onChange={(e) => setForm((f) => ({ ...f, alt_text: e.target.value }))} placeholder="Model wearing velvet durag" style={inp} />
            </div>
            <div>
              <label style={lbl}>Page</label>
              <select value={form.page} onChange={(e) => setForm((f) => ({ ...f, page: e.target.value as "collections" | "bestsellers" }))} style={inp}>
                <option value="collections">Collections</option>
                <option value="bestsellers">Bestsellers</option>
              </select>
            </div>
            <div>
              <label style={lbl}>Category (optional — leave blank for all)</label>
              <select value={form.category_id} onChange={(e) => setForm((f) => ({ ...f, category_id: e.target.value }))} style={inp}>
                <option value="">All categories</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label style={lbl}>Layout</label>
              <select value={form.position} onChange={(e) => setForm((f) => ({ ...f, position: e.target.value as "after_4" | "after_2" }))} style={inp}>
                <option value="after_4">After a row of 4 products</option>
                <option value="after_2">After 2 stacked products</option>
              </select>
            </div>
            {error && <p style={{ fontFamily: "var(--font-montserrat)", fontSize: "10px", color: "#c00" }}>{error}</p>}
            <button type="submit" disabled={saving}
              style={{ backgroundColor: "#000", color: "#fff", border: "none", padding: "0.7rem", fontFamily: "var(--font-montserrat)", fontSize: "9px", fontWeight: 600, letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer", opacity: saving ? 0.6 : 1 }}>
              {saving ? "Adding..." : "Add"}
            </button>
          </form>
        </div>

        {/* List */}
        <div style={{ backgroundColor: "#fff", border: "1px solid #e5e5e5" }}>
          <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 90px 100px 80px 60px", padding: "0.75rem 1.25rem", borderBottom: "1px solid #f0f0f0", backgroundColor: "#fafafa" }}>
            {["", "Image", "Page", "Layout", "Active", ""].map((h, i) => (
              <span key={i} style={{ fontFamily: "var(--font-montserrat)", fontSize: "9px", fontWeight: 600, letterSpacing: "0.15em", textTransform: "uppercase", color: "#888" }}>{h}</span>
            ))}
          </div>

          {loading && <p style={{ padding: "1.5rem", fontFamily: "var(--font-montserrat)", fontSize: "10px", color: "#bbb" }}>Loading...</p>}
          {!loading && editorials.length === 0 && (
            <p style={{ padding: "1.5rem", fontFamily: "var(--font-montserrat)", fontSize: "10px", color: "#bbb" }}>No editorial images yet.</p>
          )}

          {editorials.map((ed) => (
            <div key={ed.id} style={{ display: "grid", gridTemplateColumns: "60px 1fr 90px 100px 80px 60px", padding: "0.85rem 1.25rem", borderBottom: "1px solid #f0f0f0", alignItems: "center" }}>
              {/* Thumbnail */}
              <div style={{ width: "44px", height: "44px", overflow: "hidden", backgroundColor: "#f5f5f5", flexShrink: 0 }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={ed.image_url} alt={ed.alt_text} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              </div>

              {/* Alt + category */}
              <div style={{ overflow: "hidden" }}>
                <p style={{ fontFamily: "var(--font-montserrat)", fontSize: "10px", color: "#000", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{ed.alt_text || "—"}</p>
                <p style={{ fontFamily: "var(--font-montserrat)", fontSize: "9px", color: "#bbb", marginTop: "2px" }}>
                  {ed.category_id ? categories.find((c) => c.id === ed.category_id)?.name ?? ed.category_id : "All"}
                </p>
              </div>

              {/* Page */}
              <span style={{ fontFamily: "var(--font-montserrat)", fontSize: "9px", color: "#555", textTransform: "uppercase", letterSpacing: "0.08em" }}>{ed.page}</span>

              {/* Layout */}
              <span style={{ fontFamily: "var(--font-montserrat)", fontSize: "9px", color: "#555" }}>{positionLabel(ed.position)}</span>

              {/* Active toggle */}
              <button onClick={() => toggleActive(ed.id, ed.active)}
                style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", background: "none", border: `1px solid ${ed.active ? "#000" : "#e0e0e0"}`, padding: "0.35rem 0.6rem", cursor: "pointer", fontFamily: "var(--font-montserrat)", fontSize: "8px", fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: ed.active ? "#000" : "#bbb" }}>
                {ed.active ? "On" : "Off"}
              </button>

              {/* Delete */}
              <button onClick={() => handleDelete(ed.id)} style={{ background: "none", border: "none", cursor: "pointer", color: "#c62828" }}>
                <Trash2 size={13} strokeWidth={1.5} />
              </button>
            </div>
          ))}
        </div>

      </div>
    </AdminShell>
  );
}
