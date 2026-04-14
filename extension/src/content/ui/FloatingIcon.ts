export interface FloatingIconProps {
  x: number;
  y: number;
  onClick: () => void;
}

export function renderFloatingIcon(root: ShadowRoot, props: FloatingIconProps): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "vr-root";
  wrap.style.left = `${props.x}px`;
  wrap.style.top = `${props.y - 32}px`;

  const icon = document.createElement("div");
  icon.className = "vr-floating-icon";
  icon.textContent = "◉";
  icon.addEventListener("click", (e) => {
    e.stopPropagation();
    props.onClick();
  });
  wrap.appendChild(icon);

  root.appendChild(wrap);
  return wrap;
}
