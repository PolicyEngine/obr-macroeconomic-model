"use client";

import { useState, useMemo } from "react";
import SectionHeading from "./SectionHeading";

// Map full type strings to short labels + PE-token pill colours.
function typeBadge(t) {
  const s = t || "";
  if (/^ident/i.test(s)) {
    return { label: "Identity", className: "bg-primary-50 text-primary-700" };
  }
  if (/^econom/i.test(s)) {
    return { label: "Econometric", className: "bg-red-50 text-red-700" };
  }
  if (/^calib/i.test(s)) {
    return { label: "Calibrated", className: "bg-amber-50 text-amber-700" };
  }
  if (/^exog/i.test(s)) {
    return { label: "Exogenous", className: "bg-slate-100 text-slate-600" };
  }
  return { label: s || "—", className: "bg-slate-100 text-slate-600" };
}

export default function VariablesTab({ model }) {
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("");
  const [type, setType] = useState("");

  const items = model?.items || [];
  const groups = model?.groups || [];

  const rows = useMemo(() => {
    const q = search.toLowerCase().trim();
    return items.filter(
      (it) =>
        (!group || it.group === group) &&
        (!type || it.type === type) &&
        (!q ||
          (it.code || "").toLowerCase().indexOf(q) >= 0 ||
          (it.desc || "").toLowerCase().indexOf(q) >= 0),
    );
  }, [items, search, group, type]);

  return (
    <div className="space-y-6">
      <SectionHeading
        title="Model variables"
        description={
          <>
            Every variable in the model &mdash; its code, what it means, the National
            Accounts (ONS) series it maps to, and how it is determined. Search by code or
            description, or filter by group and type.
          </>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search code or description&hellip;"
          aria-label="Search variables"
          className="min-w-[220px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
        />
        <select
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          aria-label="Filter by group"
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
        >
          <option value="">All groups</option>
          {groups.filter(Boolean).map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          aria-label="Filter by type"
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
        >
          <option value="">All types</option>
          <option value="Econometrically estimated">Econometrically estimated</option>
          <option value="Identity">Identity</option>
          <option value="Calibrated/technical relationship">
            Calibrated/technical relationship
          </option>
          <option value="Exogenous">Exogenous</option>
        </select>
        <span className="ml-auto text-sm text-slate-500">
          {rows.length} of {items.length} variables
        </span>
      </div>

      <section className="section-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Description</th>
              <th>ONS series</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((it) => {
                const badge = typeBadge(it.type);
                return (
                  <tr key={it.code}>
                    <td>
                      <span className="font-mono font-semibold text-primary-700 whitespace-nowrap">
                        {it.code}
                      </span>
                    </td>
                    <td>
                      <div className="text-slate-900">{it.desc || "—"}</div>
                      {it.group ? (
                        <div className="mt-0.5 text-xs text-slate-500">{it.group}</div>
                      ) : null}
                    </td>
                    <td className="text-slate-600">{it.ons || "—"}</td>
                    <td>
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}
                      >
                        {badge.label}
                      </span>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={4} className="text-center text-slate-500">
                  No variables match your search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
