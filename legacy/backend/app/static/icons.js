export function iconSvg(name) {
  const icons = {
    mic:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><title>Microphone</title><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/><path d="M7 11.5a5 5 0 0 0 10 0" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/><path d="M12 16.5V21" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/><path d="M9 21h6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/></svg>',
    camera:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><title>Camera</title><path d="M4.5 8.5h11A2.5 2.5 0 0 1 18 11v2A2.5 2.5 0 0 1 15.5 15.5h-11A2.5 2.5 0 0 1 2 13v-2a2.5 2.5 0 0 1 2.5-2.5Z" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/><path d="m18 10 4-2v8l-4-2" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/></svg>',
    screen:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><title>Screen share</title><rect x="3" y="4" width="18" height="12" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 9v10" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/><path d="m8.5 12 3.5-3.5L15.5 12" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/><path d="M8 20h8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/></svg>',
    snapshot:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><title>Screenshot</title><path d="M8 7.5 9.3 5h5.4L16 7.5h2.5A2.5 2.5 0 0 1 21 10v6a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 16v-6a2.5 2.5 0 0 1 2.5-2.5H8Z" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/><circle cx="12" cy="13" r="3.2" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>',
    start:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><title>Start</title><path d="M9 6.5v11l8-5.5-8-5.5Z" fill="currentColor"/></svg>',
    confirm:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><title>Confirm</title><path d="m5.5 12.5 4 4 9-9" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.1"/></svg>',
    stop:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><title>Stop</title><path d="m7 7 10 10M17 7 7 17" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="2.1"/></svg>',
    analyze:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><title>Analyze</title><path d="M4 15.5V12" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/><path d="M8 18V9" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/><path d="M12 20V5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/><path d="M16 17V8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/><path d="M20 14V10" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.9"/></svg>',
  };
  return icons[name] || "";
}

export function renderButton(button, { icon, label, iconOnly = false }) {
  button.innerHTML = iconOnly
    ? `<span class="button-icon" aria-hidden="true">${iconSvg(icon)}</span><span class="sr-only">${label}</span>`
    : `<span class="button-content"><span class="button-icon" aria-hidden="true">${iconSvg(icon)}</span><span class="button-label">${label}</span></span>`;
  button.setAttribute("aria-label", label);
  button.title = label;
}
