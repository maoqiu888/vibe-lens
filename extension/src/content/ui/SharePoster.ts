import type { AnalyzeResult, Domain } from "../../shared/types";

const W = 1080;
const H = 1080;

const DOMAIN_LABEL: Record<Domain, string> = {
  book: "豆瓣读书",
  movie: "豆瓣电影",
  game: "Steam",
  music: "网易云音乐",
};

export function generatePoster(result: AnalyzeResult, sourceDomain: Domain): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;

  drawBackground(ctx);
  drawWatermark(ctx);
  drawWordmark(ctx);
  drawScore(ctx, result.match_score);
  drawTagPills(ctx, result.matched_tags.map((t) => t.name));
  drawRoast(ctx, result.roast || result.summary || "");
  drawSourceLine(ctx, sourceDomain);
  drawFooter(ctx);

  return canvas;
}

function drawBackground(ctx: CanvasRenderingContext2D) {
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, "#6c5ce7");
  grad.addColorStop(1, "#a29bfe");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
}

function drawWatermark(ctx: CanvasRenderingContext2D) {
  ctx.save();
  ctx.globalAlpha = 0.15;
  ctx.strokeStyle = "#fff";
  ctx.fillStyle = "#fff";
  const cx = 140;
  const cy = H - 140;
  [90, 60, 30].forEach((r) => {
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
  });
  ctx.beginPath();
  ctx.arc(cx, cy, 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawWordmark(ctx: CanvasRenderingContext2D) {
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.font = `bold 60px system-ui, "PingFang SC", sans-serif`;
  ctx.textBaseline = "top";
  ctx.fillText("Vibe-Lens", 60, 60);
  ctx.restore();
}

function drawScore(ctx: CanvasRenderingContext2D, score: number) {
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.font = `bold 280px system-ui, "PingFang SC", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(`${score}%`, W / 2, 340);
  ctx.restore();
}

function drawTagPills(ctx: CanvasRenderingContext2D, tagNames: string[]) {
  if (tagNames.length === 0) return;
  ctx.save();
  ctx.font = `bold 36px system-ui, "PingFang SC", sans-serif`;
  ctx.textBaseline = "middle";
  const padX = 24;
  const gap = 16;
  const pillHeight = 64;
  const y = 520;

  const widths = tagNames.map((n) => ctx.measureText(n).width + padX * 2);
  const total = widths.reduce((a, b) => a + b, 0) + gap * (tagNames.length - 1);
  let x = (W - total) / 2;

  for (let i = 0; i < tagNames.length; i++) {
    const w = widths[i];
    ctx.fillStyle = "rgba(255,255,255,0.16)";
    drawRoundedRect(ctx, x, y - pillHeight / 2, w, pillHeight, 32);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.textAlign = "center";
    ctx.fillText(tagNames[i], x + w / 2, y + 2);
    x += w + gap;
  }
  ctx.restore();
}

function drawRoast(ctx: CanvasRenderingContext2D, text: string) {
  ctx.save();
  ctx.fillStyle = "#fff";
  ctx.font = `bold 54px system-ui, "PingFang SC", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const maxWidth = W * 0.8;
  const lineHeight = 76;
  const startY = 620;
  const lines = wrapCJK(text, maxWidth, ctx);
  const visible = lines.slice(0, 3);
  for (let i = 0; i < visible.length; i++) {
    ctx.fillText(visible[i], W / 2, startY + i * lineHeight);
  }
  ctx.restore();
}

function drawSourceLine(ctx: CanvasRenderingContext2D, sourceDomain: Domain) {
  ctx.save();
  ctx.globalAlpha = 0.8;
  ctx.fillStyle = "#fff";
  ctx.font = `32px system-ui, "PingFang SC", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillText(`—— 来自 ${DOMAIN_LABEL[sourceDomain]} · 被我划了`, W / 2, H - 120);
  ctx.restore();
}

function drawFooter(ctx: CanvasRenderingContext2D) {
  ctx.save();
  ctx.globalAlpha = 0.6;
  ctx.fillStyle = "#fff";
  ctx.font = `28px system-ui, "PingFang SC", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillText("vibe-lens.local", W / 2, H - 60);
  ctx.restore();
}

function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function wrapCJK(text: string, maxWidth: number, ctx: CanvasRenderingContext2D): string[] {
  const lines: string[] = [];
  let current = "";
  for (const ch of text) {
    const test = current + ch;
    if (ctx.measureText(test).width > maxWidth && current.length > 0) {
      lines.push(current);
      current = ch;
    } else {
      current = test;
    }
  }
  if (current) lines.push(current);
  return lines;
}

export async function copyPosterToClipboard(canvas: HTMLCanvasElement): Promise<void> {
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob((b) => resolve(b), "image/png"),
  );
  if (!blob) throw new Error("canvas.toBlob returned null");
  await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
}

export function downloadPoster(canvas: HTMLCanvasElement): void {
  const link = document.createElement("a");
  link.download = `vibe-lens-${Date.now()}.png`;
  link.href = canvas.toDataURL("image/png");
  link.click();
}
