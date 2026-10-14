
async (email, code) => {
  try {
    const response = await fetch("/auth/verify", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      credentials: "same-origin",
      body: JSON.stringify({email: email || "", code: code || ""}),
    });
    if (response.ok) return __AUTH_SIGNED_IN__;
    if (response.status === 429) return __AUTH_TOO_MANY_ATTEMPTS__;
    return __AUTH_CODE_REJECTED__;
  } catch (networkError) {
    return __AUTH_VERIFY_FAILED__;
  }
}
