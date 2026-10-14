
async () => {
  try {
    await fetch("/auth/logout", {method: "POST", credentials: "same-origin"});
  } catch (networkError) {}
  return __AUTH_SIGNED_OUT__;
}
