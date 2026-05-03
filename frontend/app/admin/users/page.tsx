"use client";

import { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";

/* ─── Types ──────────────────────────────────────────────────────────── */

type UserRole = "admin" | "analyst" | "editor" | "reader";

interface UserProfile {
  id: string;
  display_name: string;
  role: UserRole;
  created_at: string;
}

/* ─── Role config ────────────────────────────────────────────────────── */

const ROLE_OPTIONS: UserRole[] = ["reader", "editor", "analyst", "admin"];

const ROLE_STYLES: Record<UserRole, string> = {
  admin: "bg-sig-high/10 text-sig-high border-sig-high/20",
  analyst: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  editor: "bg-accent-primary/10 text-accent-primary border-accent-primary/20",
  reader: "bg-text-muted/10 text-text-muted border-text-muted/20",
};

/* ─── Helpers ────────────────────────────────────────────────────────── */

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

/* ─── Component ──────────────────────────────────────────────────────── */

export default function UsersPage() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Confirmation dialog state
  const [confirmChange, setConfirmChange] = useState<{
    userId: string;
    userName: string;
    newRole: UserRole;
  } | null>(null);
  const [updating, setUpdating] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/users");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setUsers(json.users ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Handle role change (with confirmation)
  function requestRoleChange(user: UserProfile, newRole: UserRole) {
    if (newRole === user.role) return;
    setConfirmChange({
      userId: user.id,
      userName: user.display_name,
      newRole,
    });
  }

  async function confirmRoleChange() {
    if (!confirmChange) return;
    setUpdating(true);
    try {
      const res = await fetch(`/api/admin/users/${confirmChange.userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: confirmChange.newRole }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setConfirmChange(null);
      await fetchUsers();
    } catch (err) {
      console.error("Failed to update role:", err);
    } finally {
      setUpdating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="font-mono text-sm text-text-muted">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="font-mono text-sm text-accent-danger">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page title */}
      <h1 className="font-serif text-[28px] text-text-bright">User Management</h1>

      {/* ── Users Table ────────────────────────────────────────────── */}
      <div className="rounded-sm border border-border-primary bg-bg-secondary">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border-primary text-left">
              <th className="px-4 py-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                Display Name
              </th>
              <th className="px-4 py-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted">
                Role
              </th>
              <th className="px-4 py-3 font-mono text-[12px] font-bold uppercase tracking-[0.15em] text-text-muted text-right">
                Created
              </th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr
                key={user.id}
                className="border-b border-border-primary/50 last:border-0"
              >
                <td className="px-4 py-3 font-mono text-[14px] text-text-primary">
                  {user.display_name}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    {ROLE_OPTIONS.map((role) => (
                      <button
                        key={role}
                        type="button"
                        onClick={() => requestRoleChange(user, role)}
                        className={cn(
                          "rounded-sm border px-2 py-0.5 font-mono text-[12px] transition-colors",
                          user.role === role
                            ? ROLE_STYLES[role]
                            : "bg-transparent text-text-muted/40 border-border-primary/50 hover:text-text-muted hover:border-border-primary"
                        )}
                      >
                        {role}
                      </button>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-[13px] text-text-muted text-right">
                  {formatDate(user.created_at)}
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td
                  colSpan={3}
                  className="px-4 py-8 text-center font-mono text-sm text-text-muted"
                >
                  No users found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ── Confirmation Dialog ────────────────────────────────────── */}
      {confirmChange && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="mx-4 w-full max-w-sm rounded-sm border border-border-primary bg-bg-secondary p-6">
            <h3 className="font-serif text-lg text-text-bright mb-3">
              Confirm Role Change
            </h3>
            <p className="text-sm text-text-secondary">
              Change{" "}
              <span className="font-mono text-text-primary">
                {confirmChange.userName}
              </span>
              &apos;s role to{" "}
              <span
                className={cn(
                  "font-mono font-bold",
                  confirmChange.newRole === "admin"
                    ? "text-sig-high"
                    : "text-text-muted"
                )}
              >
                {confirmChange.newRole}
              </span>
              ?
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmChange(null)}
                className="rounded-sm border border-border-primary bg-bg-tertiary px-4 py-2 font-mono text-[13px] text-text-muted hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmRoleChange}
                disabled={updating}
                className="rounded-sm bg-accent-primary px-4 py-2 font-mono text-[13px] text-white hover:bg-accent-primary/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {updating ? "Updating..." : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
