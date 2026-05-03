import { Resend } from "resend";
import type { SupabaseClient } from "@supabase/supabase-js";

const DEFAULT_NOTIFY_EMAIL = "Brayan.Vahdat@mbzuai.ac.ae";
const DEFAULT_FROM_EMAIL = "Intelligence Brief <onboarding@resend.dev>";
const UNKNOWN_USER = "Unknown user";
const SITE_URL = (
  process.env.SITE_URL ??
  process.env.NEXT_PUBLIC_SITE_URL ??
  "https://mbzuai-intel.com"
).replace(/\/$/, "");
const ADMIN_URL = `${SITE_URL}/admin/research`;

interface ResearchRequestEmailParams {
  itemId: string;
  briefDate: string;
  requestNote: string | null;
  userId: string;
}

/**
 * Look up the item headline and section from the brief's raw_json
 * stored in the briefs table.
 */
async function resolveItemContext(
  supabase: SupabaseClient,
  briefDate: string,
  itemId: string
): Promise<{ headline: string; section: string }> {
  const { data } = await supabase
    .from("briefs")
    .select("raw_json")
    .eq("brief_date", briefDate)
    .single();

  if (!data?.raw_json) {
    return { headline: itemId, section: "Unknown" };
  }

  const rawJson = data.raw_json as { items?: Array<{ id: string; headline?: string; section?: string }> };
  const item = rawJson.items?.find((i) => i.id === itemId);

  return {
    headline: item?.headline ?? itemId,
    section: item?.section ?? "Unknown",
  };
}

/**
 * Look up the requester's display name from the user_profiles table.
 */
async function resolveUserName(
  supabase: SupabaseClient,
  userId: string
): Promise<string> {
  const { data, error } = await supabase
    .from("user_profiles")
    .select("display_name")
    .eq("id", userId)
    .maybeSingle();

  if (error) {
    console.warn("[email] Failed to resolve requester name:", error.message);
    return UNKNOWN_USER;
  }

  return data?.display_name ?? UNKNOWN_USER;
}

/**
 * Build the HTML email body with dark-themed styling matching
 * the intelligence briefing aesthetic.
 */
function buildEmailHtml(params: {
  headline: string;
  section: string;
  requesterName: string;
  requestNote: string | null;
  briefDate: string;
}): string {
  const { headline, section, requesterName, requestNote, briefDate } = params;

  const formattedDate = new Date(briefDate + "T00:00:00").toLocaleDateString(
    "en-US",
    { year: "numeric", month: "long", day: "numeric" }
  );

  const noteBlock = requestNote
    ? `
    <tr>
      <td style="padding: 16px 24px 0;">
        <p style="margin: 0 0 6px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #64748B;">
          Note
        </p>
        <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 14px; color: #CBD5E1; font-style: italic; line-height: 1.5;">
          &ldquo;${escapeHtml(requestNote)}&rdquo;
        </p>
      </td>
    </tr>`
    : "";

  return `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin: 0; padding: 0; background-color: #0A0F1C; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #0A0F1C;">
    <tr>
      <td align="center" style="padding: 40px 16px;">
        <table role="presentation" width="520" cellpadding="0" cellspacing="0" style="background-color: #111827; border: 1px solid #1E293B; border-radius: 4px;">

          <!-- Header -->
          <tr>
            <td style="padding: 24px 24px 16px; border-bottom: 1px solid #1E293B;">
              <p style="margin: 0 0 4px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase; color: #3B82F6;">
                Research Request
              </p>
              <p style="margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: 18px; color: #F1F5F9; line-height: 1.35;">
                ${escapeHtml(headline)}
              </p>
            </td>
          </tr>

          <!-- Details -->
          <tr>
            <td style="padding: 16px 24px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="50%" valign="top">
                    <p style="margin: 0 0 6px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #64748B;">
                      Section
                    </p>
                    <p style="margin: 0; font-size: 13px; color: #CBD5E1;">
                      ${escapeHtml(section)}
                    </p>
                  </td>
                  <td width="50%" valign="top">
                    <p style="margin: 0 0 6px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #64748B;">
                      Brief Date
                    </p>
                    <p style="margin: 0; font-size: 13px; color: #CBD5E1;">
                      ${formattedDate}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding: 16px 24px 0;">
              <p style="margin: 0 0 6px; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: #64748B;">
                Requested By
              </p>
              <p style="margin: 0; font-size: 13px; color: #CBD5E1;">
                ${escapeHtml(requesterName)}
              </p>
            </td>
          </tr>

          ${noteBlock}

          <!-- CTA -->
          <tr>
            <td style="padding: 24px;">
              <a href="${ADMIN_URL}" style="display: inline-block; padding: 10px 20px; background-color: #3B82F6; color: #FFFFFF; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 12px; letter-spacing: 0.05em; text-decoration: none; border-radius: 3px;">
                View in Admin
              </a>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 16px 24px; border-top: 1px solid #1E293B;">
              <p style="margin: 0; font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; font-size: 10px; color: #475569; letter-spacing: 0.05em;">
                MBZUAI Intelligence Briefing System
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>`.trim();
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/**
 * Send a research request notification email via Resend.
 *
 * Returns true when Resend accepts the email, false when delivery
 * is skipped or rejected.
 */
export async function sendResearchRequestEmail(
  supabase: SupabaseClient,
  params: ResearchRequestEmailParams
): Promise<boolean> {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.warn("[email] RESEND_API_KEY not set — skipping email notification");
    return false;
  }

  const notifyEmail = process.env.RESEND_NOTIFY_EMAIL ?? DEFAULT_NOTIFY_EMAIL;
  const fromEmail = process.env.RESEND_FROM_EMAIL ?? DEFAULT_FROM_EMAIL;

  if (!process.env.RESEND_FROM_EMAIL) {
    console.warn(
      "[email] RESEND_FROM_EMAIL not set — using Resend's onboarding sender. " +
        "Production delivery may fail until a verified sender is configured."
    );
  }

  // Resolve context in parallel
  const [{ headline, section }, requesterName] = await Promise.all([
    resolveItemContext(supabase, params.briefDate, params.itemId),
    resolveUserName(supabase, params.userId),
  ]);

  const resend = new Resend(apiKey);

  const { data, error } = await resend.emails.send({
    from: fromEmail,
    to: notifyEmail,
    subject: `Research Request: ${headline}`,
    html: buildEmailHtml({
      headline,
      section,
      requesterName,
      requestNote: params.requestNote,
      briefDate: params.briefDate,
    }),
  });

  if (error) {
    console.error("[email] Resend API error:", {
      message: error.message,
      name: error.name,
      notifyEmail,
      fromEmail,
    });
    return false;
  }

  console.log("[email] Research request notification sent:", {
    emailId: data?.id ?? null,
    headline,
    notifyEmail,
    fromEmail,
  });
  return true;
}
