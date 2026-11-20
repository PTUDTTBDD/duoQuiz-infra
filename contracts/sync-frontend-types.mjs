import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const contractPath = path.resolve(__dirname, "openapi.json");
const frontendRoot = path.resolve(__dirname, "../../duoQuiz-frontend");
const frontendOutputPath = path.resolve(frontendRoot, "src/api/generated/schema.d.ts");

if (!fs.existsSync(contractPath)) {
  console.error(`Missing OpenAPI contract at ${contractPath}. Run backend openapi export first.`);
  process.exit(1);
}

fs.mkdirSync(path.dirname(frontendOutputPath), { recursive: true });
const binName = process.platform === "win32" ? "openapi-typescript.cmd" : "openapi-typescript";
const localBin = path.resolve(frontendRoot, "node_modules/.bin", binName);
const cmd = fs.existsSync(localBin)
  ? `"${localBin}" "${contractPath}" -o "${frontendOutputPath}"`
  : `npx openapi-typescript "${contractPath}" -o "${frontendOutputPath}"`;

execSync(cmd, { stdio: "inherit" });
console.log(`Synced TypeScript API schema to ${frontendOutputPath}`);
