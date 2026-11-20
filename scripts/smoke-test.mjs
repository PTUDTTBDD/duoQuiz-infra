const baseUrl = process.env.API_URL ?? "http://localhost:4000/api/v1";

async function main() {
  const res = await fetch(`${baseUrl}/health`);
  const body = await res.json();
  console.log("Health status:", res.status, JSON.stringify(body, null, 2));
  if (!res.ok) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error("Smoke test failed:", err);
  process.exit(1);
});

