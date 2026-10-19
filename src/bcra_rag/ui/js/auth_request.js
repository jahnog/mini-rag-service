
async (email) => {
  const sendingMessage = __AUTH_SENDING__;
  const smtpOkMessage = __AUTH_SMTP_OK__;
  const smtpFailMessage = __AUTH_SMTP_FAIL__;
  const smtpProblemMessage = __AUTH_SMTP_PROBLEM__;
  const tooManyAttemptsMessage = __AUTH_TOO_MANY_ATTEMPTS__;
  const invalidOriginMessage = __AUTH_INVALID_ORIGIN__;
  const invalidEmailMessage = __AUTH_INVALID_EMAIL__;
  const okClass = "auth-status-ok";
  const errorClass = "auth-status-err";
  const sendButton = document.querySelector("#auth-send button")
    || document.querySelector("#auth-send");
  const statusHost = document.querySelector("#auth-status");
  if (statusHost && !statusHost.getAttribute("aria-live")) {
    statusHost.setAttribute("aria-live", "polite");
  }
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
    } else if (response.status === 403) {
      statusMessage = invalidOriginMessage;
      statusKind = "idle";
    } else if (response.status === 422) {
      statusMessage = invalidEmailMessage;
      statusKind = "idle";
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
  }
  if (sendButton) sendButton.disabled = false;
  showStatus(statusMessage, statusKind);
  return statusMessage;
}
