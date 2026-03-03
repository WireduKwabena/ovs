import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");

const openApiPath = path.resolve(repoRoot, "backend", "openapi.yaml");
const servicesDir = path.resolve(repoRoot, "frontend", "src", "services");

const hasFlag = (flag) => process.argv.includes(flag);

const toSet = (items) => new Set(items);

const normalizePath = (rawPath) => {
  if (!rawPath) return "";
  let value = String(rawPath).trim();
  if (!value) return "";

  if (/^https?:\/\//i.test(value)) {
    try {
      const parsed = new URL(value);
      value = parsed.pathname || "";
    } catch {
      return "";
    }
  }

  value = value.split("?")[0].trim();
  value = value.replace(/\$\{[^}]+\}/g, "{var}");
  value = value.replace(/\{[^}]+\}/g, "{var}");

  if (value.startsWith("/api/")) {
    value = value.slice(4);
  } else if (value === "/api") {
    value = "/";
  }

  if (!value.startsWith("/")) {
    value = `/${value}`;
  }

  value = value.replace(/\/{2,}/g, "/");
  if (value.length > 1 && value.endsWith("/")) {
    value = value.slice(0, -1);
  }
  return value;
};

const ignorePath = (normalizedPath) => {
  const ignoredPatterns = [
    /^\/$/,
    /^\/schema(?:\/.*)?$/,
    /^\/background-checks\/providers\/\{var\}\/webhook$/,
    /^\/billing\/subscriptions\/stripe\/webhook$/,
    /^\/ml-monitoring\/metrics(?:\/.*)?$/,
  ];
  return ignoredPatterns.some((pattern) => pattern.test(normalizedPath));
};

const parseOpenApiPaths = () => {
  if (!fs.existsSync(openApiPath)) {
    throw new Error(`OpenAPI file not found at ${openApiPath}`);
  }

  const content = fs.readFileSync(openApiPath, "utf8");
  const matches = [...content.matchAll(/^  (\/api\/[^:]+):\s*$/gm)];
  return matches
    .map((match) => normalizePath(match[1]))
    .filter((item) => item && !ignorePath(item));
};

const parseServiceEndpointsFromSource = (source) => {
  const endpoints = [];
  const methodPattern = /api\.(?:get|post|put|patch|delete)\b/g;
  const length = source.length;

  const skipWhitespace = (start) => {
    let cursor = start;
    while (cursor < length && /\s/.test(source[cursor])) {
      cursor += 1;
    }
    return cursor;
  };

  const skipGeneric = (start) => {
    let cursor = start;
    if (source[cursor] !== "<") {
      return cursor;
    }
    let depth = 0;
    while (cursor < length) {
      const char = source[cursor];
      if (char === "<") {
        depth += 1;
      } else if (char === ">") {
        depth -= 1;
        if (depth === 0) {
          cursor += 1;
          break;
        }
      } else if (char === "'" || char === '"' || char === "`") {
        const quote = char;
        cursor += 1;
        while (cursor < length) {
          if (source[cursor] === "\\" && cursor + 1 < length) {
            cursor += 2;
            continue;
          }
          if (source[cursor] === quote) {
            cursor += 1;
            break;
          }
          cursor += 1;
        }
        continue;
      }
      cursor += 1;
    }
    return cursor;
  };

  for (const match of source.matchAll(methodPattern)) {
    let cursor = skipWhitespace(match.index + match[0].length);
    cursor = skipGeneric(cursor);
    cursor = skipWhitespace(cursor);

    if (source[cursor] !== "(") {
      continue;
    }
    cursor = skipWhitespace(cursor + 1);

    const quote = source[cursor];
    if (!["'", '"', "`"].includes(quote)) {
      continue;
    }
    cursor += 1;

    const start = cursor;
    while (cursor < length) {
      const char = source[cursor];
      if (char === "\\" && cursor + 1 < length) {
        cursor += 2;
        continue;
      }
      if (char === quote) {
        break;
      }
      cursor += 1;
    }

    const raw = source.slice(start, cursor);
    const normalized = normalizePath(raw);
    if (normalized && !ignorePath(normalized)) {
      endpoints.push(normalized);
    }
  }

  return endpoints;
};

const parseServicePaths = () => {
  if (!fs.existsSync(servicesDir)) {
    throw new Error(`Services directory not found at ${servicesDir}`);
  }

  const files = fs
    .readdirSync(servicesDir)
    .filter((name) => name.endsWith(".ts"))
    .map((name) => path.join(servicesDir, name));

  const byFile = {};
  for (const filePath of files) {
    const content = fs.readFileSync(filePath, "utf8");
    const normalized = parseServiceEndpointsFromSource(content);
    byFile[path.basename(filePath)] = Array.from(new Set(normalized)).sort();
  }

  const combined = Object.values(byFile).flat();
  return {
    byFile,
    all: Array.from(new Set(combined)).sort(),
  };
};

const main = () => {
  const openApiPaths = parseOpenApiPaths();
  const openApiSet = toSet(openApiPaths);
  const serviceData = parseServicePaths();
  const serviceSet = toSet(serviceData.all);

  const covered = Array.from(openApiSet).filter((pathKey) => serviceSet.has(pathKey)).sort();
  const missing = Array.from(openApiSet).filter((pathKey) => !serviceSet.has(pathKey)).sort();

  console.log("Endpoint Coverage Report");
  console.log("========================");
  console.log(`OpenAPI paths considered : ${openApiSet.size}`);
  console.log(`Frontend service paths   : ${serviceSet.size}`);
  console.log(`Covered paths            : ${covered.length}`);
  console.log(`Missing paths            : ${missing.length}`);

  const coveragePct = openApiSet.size === 0 ? 100 : (covered.length / openApiSet.size) * 100;
  console.log(`Coverage                 : ${coveragePct.toFixed(2)}%`);

  if (hasFlag("--show-services")) {
    console.log("\nService paths by file");
    console.log("---------------------");
    for (const [fileName, endpoints] of Object.entries(serviceData.byFile)) {
      console.log(`${fileName}: ${endpoints.length}`);
      for (const endpoint of endpoints) {
        console.log(`  - ${endpoint}`);
      }
    }
  }

  if (hasFlag("--show-missing")) {
    console.log("\nMissing paths");
    console.log("-------------");
    for (const item of missing) {
      console.log(`- ${item}`);
    }
  }

  if (hasFlag("--strict") && missing.length > 0) {
    process.exitCode = 1;
  }
};

main();
