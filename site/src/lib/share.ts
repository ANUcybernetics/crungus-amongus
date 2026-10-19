// Sharing an item's permalink: the system share sheet on touch devices, where
// it is the familiar way to send a link anywhere; elsewhere the clipboard, with
// a toast to say so. Runs in the browser only.

const TOAST_MS = 2200;

function toast(text: string): void {
  // inside a modal dialog or fullscreen element, or the toast would draw behind it
  const host =
    document.querySelector("dialog[open]") ?? document.fullscreenElement ?? document.body;
  const note = host.querySelector<HTMLElement>(":scope > .toast") ?? document.createElement("p");
  if (!note.isConnected) {
    note.className = "toast mono";
    note.setAttribute("role", "status");
    host.append(note);
  }
  note.textContent = text;
  note.classList.add("shown");
  window.clearTimeout(Number(note.dataset.timer));
  note.dataset.timer = String(window.setTimeout(() => note.classList.remove("shown"), TOAST_MS));
}

export async function shareLink(href: string, title: string): Promise<void> {
  const url = new URL(href, location.href).href;
  if ("share" in navigator && matchMedia("(pointer: coarse)").matches) {
    try {
      await navigator.share({ url, title });
      return;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      // anything else (no permission, say) falls through to the clipboard
    }
  }
  try {
    await navigator.clipboard.writeText(url);
    toast("link copied");
  } catch {
    // no clipboard access either: show the link to copy by hand
    window.prompt("copy this link", url);
  }
}

/** Wire every `button[data-share]` under `root` to share its link. */
export function bindShareButtons(root: ParentNode = document): void {
  for (const button of root.querySelectorAll<HTMLButtonElement>("button[data-share]")) {
    button.addEventListener("click", () => {
      void shareLink(button.dataset.share!, button.dataset.title ?? document.title);
    });
  }
}
