"use client";
import { useState, useMemo } from "react";
import SectionHeading from "./SectionHeading";

// Map an item's `type` to a short label + Tailwind pill classes (PE tokens),
// mirroring the original dashboard's typeClass/typeShort helpers.
function typeBadge(type) {
  const t = type || "";
  if (/^ident/i.test(t)) {
    return { label: "Identity", className: "bg-primary-50 text-primary-700" };
  }
  if (/^econom/i.test(t)) {
    return { label: "Econometric", className: "bg-red-50 text-red-700" };
  }
  if (/^calib/i.test(t)) {
    return { label: "Calibrated", className: "bg-amber-50 text-amber-700" };
  }
  if (/^exog/i.test(t)) {
    return { label: "Exogenous", className: "bg-slate-100 text-slate-600" };
  }
  return { label: t || "—", className: "bg-slate-100 text-slate-600" };
}

export default function EquationsTab({ model }) {
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("");
  const [showPy, setShowPy] = useState(true);

  const items = (model && model.items) || [];
  const groups = ((model && model.groups) || []).filter(Boolean);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return items.filter(
      (it) =>
        it.eq &&
        (!group || it.group === group) &&
        (!q ||
          (it.code || "").toLowerCase().indexOf(q) >= 0 ||
          (it.desc || "").toLowerCase().indexOf(q) >= 0)
    );
  }, [items, search, group]);

  return (
    <div className="space-y-6">
      <section className="section-card">
        <SectionHeading
          title="Model equations"
          description="Browse every behavioural and identity equation in the model, shown as published EViews code alongside the transpiled Python the dashboard runs."
        />

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search code or description…"
            aria-label="Search equations"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
          />
          <select
            value={group}
            onChange={(e) => setGroup(e.target.value)}
            aria-label="Filter by group"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
          >
            <option value="">All groups</option>
            {groups.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={showPy}
              onChange={(e) => setShowPy(e.target.checked)}
            />
            show transpiled Python
          </label>
          <span className="text-sm text-slate-500">
            {filtered.length} equations
          </span>
        </div>

        {filtered.length ? (
          <div className="flex flex-col gap-3">
            {filtered.map((it) => {
              const badge = typeBadge(it.type);
              return (
                <div
                  key={it.code}
                  className="rounded-2xl border border-slate-200 bg-white p-4"
                >
                  <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="font-mono font-semibold text-primary-700">
                      {it.code}
                    </span>
                    {it.desc ? (
                      <span className="text-sm text-slate-700">{it.desc}</span>
                    ) : null}
                    <span
                      className={`rounded-md px-2 py-1 text-xs font-semibold ${badge.className}`}
                    >
                      {badge.label}
                    </span>
                    <span className="text-xs text-slate-400">{it.group}</span>
                  </div>

                  <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100">
                    {it.eq}
                  </pre>

                  {showPy && it.py ? (
                    <>
                      <div className="mb-1 mt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Transpiled Python
                      </div>
                      <pre
                        className="overflow-x-auto whitespace-pre-wrap break-words rounded-xl p-3 font-mono text-xs leading-relaxed text-slate-100"
                        style={{ backgroundColor: "#0a2a27" }}
                      >
                        {it.py}
                      </pre>
                    </>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            No equations match your search.
          </p>
        )}
      </section>
    </div>
  );
}
