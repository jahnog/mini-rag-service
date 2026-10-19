
async () => {
  document.querySelector("#auth-status")?.classList.remove("auth-status-ok", "auth-status-err");
  try {
    await fetch("/auth/logout", {method: "POST", credentials: "same-origin"});
  } catch (networkError) {}
  return __AUTH_SIGNED_OUT__;
}
