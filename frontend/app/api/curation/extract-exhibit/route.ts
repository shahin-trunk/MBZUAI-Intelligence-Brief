import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import { getCurationClient } from "@/lib/api/curation-helpers";
import { formatExhibit } from "@/lib/utils/exhibit-formatter";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/jpg", "image/webp"];

type AnthropicImageMediaType = "image/png" | "image/jpeg" | "image/webp" | "image/gif";

/**
 * Detect the true image media type from the file's magic bytes.
 * Browsers set File.type from the extension/drag source, which can lie
 * (e.g. a JPEG saved as .png). Anthropic's API validates the actual
 * bytes against the declared media_type, so we must sniff.
 */
function sniffImageMediaType(buf: Buffer): AnthropicImageMediaType | null {
  if (buf.length < 12) return null;
  // PNG: 89 50 4E 47 0D 0A 1A 0A
  if (
    buf[0] === 0x89 &&
    buf[1] === 0x50 &&
    buf[2] === 0x4e &&
    buf[3] === 0x47
  )
    return "image/png";
  // JPEG: FF D8 FF
  if (buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return "image/jpeg";
  // WebP: "RIFF"...."WEBP"
  if (
    buf[0] === 0x52 &&
    buf[1] === 0x49 &&
    buf[2] === 0x46 &&
    buf[3] === 0x46 &&
    buf[8] === 0x57 &&
    buf[9] === 0x45 &&
    buf[10] === 0x42 &&
    buf[11] === 0x50
  )
    return "image/webp";
  // GIF: "GIF8"
  if (
    buf[0] === 0x47 &&
    buf[1] === 0x49 &&
    buf[2] === 0x46 &&
    buf[3] === 0x38
  )
    return "image/gif";
  return null;
}

const EXTRACTION_PROMPT = `You are a data extraction specialist. Examine this image and extract any structured data it contains.

1. Determine the exhibit type:
   - "benchmark_table": Performance benchmark scores comparing models
   - "comparison_table": Side-by-side feature/spec/term comparisons
   - "metric_highlight": A standout number or small set of key figures
   - "timeline": Sequence of dated events
   - "none": Image doesn't contain extractable structured data

2. Extract ALL data faithfully — numbers, labels, column headers, row names — exactly as they appear. Do not round, approximate, or infer missing values.

3. Return JSON matching one of these schemas:

benchmark_table:
{"type":"benchmark_table","data":{"title":"...","columns":["Model A","Model B"],"rows":[{"benchmark":"MMLU","scores":{"Model A":"85.2%","Model B":"82.1%"}}]}}

comparison_table:
{"type":"comparison_table","data":{"title":"...","columns":["Feature","Option A","Option B"],"rows":[{"Feature":"Price","Option A":"$10","Option B":"$20"}]}}

metric_highlight:
{"type":"metric_highlight","data":{"metrics":[{"label":"Revenue","value":"$4.2B","change":"+12%"}]}}

timeline:
{"type":"timeline","data":{"events":[{"date":"2026-01","description":"Event description"}]}}

none:
{"type":"none","reason":"Brief description of why data cannot be extracted"}

Return ONLY valid JSON, no markdown fences.`;

export async function POST(request: NextRequest) {
  const { supabase } = await getCurationClient();

  const formData = await request.formData();
  const file = formData.get("image") as File | null;
  const itemId = formData.get("item_id") as string | null;
  const headline = formData.get("headline") as string | null;

  if (!file) {
    return NextResponse.json({ error: "No image file provided" }, { status: 400 });
  }

  if (!ALLOWED_TYPES.includes(file.type)) {
    return NextResponse.json(
      { error: `Invalid file type: ${file.type}. Allowed: png, jpg, webp` },
      { status: 400 },
    );
  }

  if (file.size > MAX_FILE_SIZE) {
    return NextResponse.json({ error: "File too large (max 10MB)" }, { status: 400 });
  }

  // 1. Upload to Supabase Storage
  const fileBuffer = Buffer.from(await file.arrayBuffer());
  const ext = file.name.split(".").pop() ?? "png";
  const storagePath = `${itemId ?? "unknown"}/${crypto.randomUUID()}.${ext}`;

  const { error: uploadErr } = await supabase.storage
    .from("exhibit-images")
    .upload(storagePath, fileBuffer, {
      contentType: file.type,
      upsert: false,
    });

  if (uploadErr) {
    return NextResponse.json(
      { error: `Upload failed: ${uploadErr.message}` },
      { status: 500 },
    );
  }

  const { data: urlData } = supabase.storage
    .from("exhibit-images")
    .getPublicUrl(storagePath);
  const imageUrl = urlData.publicUrl;

  // 2. Send to Claude Vision for extraction
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { exhibit: null, image_url: imageUrl, error: "ANTHROPIC_API_KEY not configured" },
    );
  }

  const client = new Anthropic({ apiKey });
  const base64 = fileBuffer.toString("base64");

  // Sniff magic bytes — browsers lie about file.type based on extension.
  // Anthropic validates bytes against declared media_type and 400s on mismatch.
  const sniffedType = sniffImageMediaType(fileBuffer);
  if (!sniffedType) {
    return NextResponse.json({
      exhibit: {
        type: "raw_image",
        data: { image_url: imageUrl, caption: "" },
        source_image_url: imageUrl,
      },
      image_url: imageUrl,
      extraction_failed: true,
      reason: "Could not detect image format from file contents",
    });
  }

  const contextHint = headline
    ? `\n\nContext: This image is from a brief item with headline: "${headline}"`
    : "";

  try {
    const response = await client.messages.create({
      model: "claude-sonnet-4-6",
      max_tokens: 2000,
      messages: [
        {
          role: "user",
          content: [
            {
              type: "image",
              source: {
                type: "base64",
                media_type: sniffedType,
                data: base64,
              },
            },
            {
              type: "text",
              text: EXTRACTION_PROMPT + contextHint,
            },
          ],
        },
      ],
    });

    const text =
      response.content[0].type === "text" ? response.content[0].text : "";
    const cleaned = text
      .replace(/```json\s*/g, "")
      .replace(/```\s*/g, "")
      .trim();
    const parsed = JSON.parse(cleaned);

    if (parsed.type === "none") {
      // Fallback to raw_image. This is a valid outcome, not an error —
      // the image just didn't fit any structured schema.
      return NextResponse.json({
        exhibit: {
          type: "raw_image",
          data: { image_url: imageUrl, caption: "" },
          source_image_url: imageUrl,
        },
        image_url: imageUrl,
      });
    }

    // Format exhibit for card display — abbreviate benchmark names,
    // cap columns, clean cell values. Deterministic post-processing
    // so the card renders well regardless of what Claude extracted.
    const formatted = formatExhibit(parsed);

    // Success — return structured exhibit with source image reference
    return NextResponse.json({
      exhibit: {
        ...formatted,
        source_image_url: imageUrl,
      },
      image_url: imageUrl,
    });
  } catch (e) {
    // Log the raw error server-side for debugging.
    console.error("[extract-exhibit] Vision API failed:", e);
    const rawMessage = e instanceof Error ? e.message : String(e);
    // Translate known API errors to a human-readable message. The Anthropic
    // SDK throws errors whose .message is the raw JSON response body.
    let reason = "We couldn't auto-extract data from this image.";
    if (/image\/\w+ media type/i.test(rawMessage)) {
      reason = "The image format wasn't recognized by the extraction service.";
    } else if (/rate.?limit/i.test(rawMessage)) {
      reason = "Extraction service is rate-limited. Try again shortly.";
    } else if (/timeout/i.test(rawMessage)) {
      reason = "Extraction timed out. The image will be saved as-is.";
    }
    return NextResponse.json({
      exhibit: {
        type: "raw_image",
        data: { image_url: imageUrl, caption: "" },
        source_image_url: imageUrl,
      },
      image_url: imageUrl,
      extraction_failed: true,
      reason,
    });
  }
}
