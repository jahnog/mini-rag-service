
async (email) => {
  const genericMessage = __AUTH_GENERIC__;
  const sendingMessage = __AUTH_SENDING__;
  const smtpOkMessage = __AUTH_SMTP_OK__;
  const smtpFailMessage = __AUTH_SMTP_FAIL__;
  const smtpProblemMessage = __AUTH_SMTP_PROBLEM__;
  const tooManyAttemptsMessage = __AUTH_TOO_MANY_ATTEMPTS__;
  const invalidOriginMessage = __AUTH_INVALID_ORIGIN__;
  const invalidEmailMessage = __AUTH_INVALID_EMAIL__;
  const flashDurationMs = __AUTH_FLASH_MS__;
  const okClass = "auth-status-ok";
  const errorClass = "auth-status-err";
  // Each click bumps the token so a late timer from an older click does nothing.
  const thisRequestToken = (window.__authSendToken = (window.__authSendToken || 0) + 1);
  const sendButton = document.querySelector("#auth-send button")
    || document.querySelector("#auth-send");
  const statusHost = document.querySelector("#auth-status");
  if (statusHost && !statusHost.getAttribute("aria-live")) {
    statusHost.setAttribute("aria-live", "polite");
  }
  const readStatusText = () => {
    const node = document.querySelector(
      "#auth-status p, #auth-status .md, #auth-status"
    );
    return (node && node.textContent ? node.textContent : "").trim();
  };
  const showStatus = (text, statusKind) => {
    const root = document.querySelector("#auth-status");
    if (!root) return;
    root.classList.remove(okClass, errorClass);
    if (statusKind === "ok") root.classList.add(okClass);
    if (statusKind === "err") root.classList.add(errorClass);
    const node = root.querySelector("p") || root.querySelector(".md");
    if (node) node.textContent = text;
  };
  if (sendButton) sendButton.disabled = true;
  showStatus(sendingMessage, "idle");
  let statusMessage = smtpFailMessage;
  let statusKind = "err";
  let shouldFlashStatus = true;
  try {
    const response = await fetch("/auth/request", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      credentials: "same-origin",
      body: JSON.stringify({email: email || ""}),
    });
    if (response.ok) {
      statusMessage = smtpOkMessage;
      statusKind = "ok";
    } else if (response.status === 429) {
      statusMessage = tooManyAttemptsMessage;
      statusKind = "idle";
      shouldFlashStatus = false;
    } else if (response.status === 403) {
      statusMessage = invalidOriginMessage;
      statusKind = "idle";
      shouldFlashStatus = false;
    } else if (response.status === 422) {
      statusMessage = invalidEmailMessage;
      statusKind = "idle";
      shouldFlashStatus = false;
    } else if (response.status === 503) {
      statusMessage = smtpFailMessage;
      statusKind = "err";
    } else {
      statusMessage = smtpProblemMessage;
      statusKind = "err";
    }
  } catch (networkError) {
    statusMessage = smtpProblemMessage;
    statusKind = "err";
    shouldFlashStatus = true;
  }
  if (sendButton) sendButton.disabled = false;
  showStatus(statusMessage, statusKind);
  if (shouldFlashStatus) {
    setTimeout(() => {
      if (thisRequestToken !== window.__authSendToken) return;
      const root = document.querySelector("#auth-status");
      if (!root) return;
      root.classList.toggle(okClass, statusKind === "ok");
      root.classList.toggle(errorClass, statusKind === "err");
    }, 0);
    setTimeout(() => {
      if (thisRequestToken !== window.__authSendToken) return;
      if (readStatusText() !== statusMessage) return;
      showStatus(genericMessage, "idle");
    }, flashDurationMs);
  }
  return statusMessage;
}
