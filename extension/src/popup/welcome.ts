export function renderWelcome(root: HTMLElement): void {
  root.innerHTML = `
    <div class="vr-welcome">
      <div class="vr-welcome-logo">◉ ◉ ◉</div>
      <h2>Vibe-Lens</h2>
      <p class="vr-welcome-tagline">我会通过你的真实行为认识你</p>
      <p class="vr-welcome-hint">
        去下列任意网站划一段文字，<br>
        让我从你的第一口开始了解你。
      </p>
      <ul class="vr-welcome-sites">
        <li>📚 豆瓣读书</li>
        <li>🎬 豆瓣电影</li>
        <li>🎮 Steam</li>
        <li>🎵 网易云音乐</li>
      </ul>
    </div>
  `;
}
