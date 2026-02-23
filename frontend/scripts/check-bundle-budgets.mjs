import fs from 'node:fs'
import path from 'node:path'

const KIB = 1024

const budgets = [
  { label: 'Main app chunk', pattern: /^index-.*\.js$/, maxBytes: 130 * KIB },
  { label: 'HR dashboard route chunk', pattern: /^HrDashboardPage-.*\.js$/, maxBytes: 30 * KIB },
  { label: 'Interview route chunk', pattern: /^HeyGenInterrogation-.*\.js$/, maxBytes: 40 * KIB },
  { label: 'React core vendor chunk', pattern: /^react-core-.*\.js$/, maxBytes: 220 * KIB },
  { label: 'State/data vendor chunk', pattern: /^state-data-.*\.js$/, maxBytes: 120 * KIB },
  { label: 'UI kit vendor chunk', pattern: /^ui-kit-.*\.js$/, maxBytes: 170 * KIB },
  { label: 'Recharts vendor chunk', pattern: /^recharts-.*\.js$/, maxBytes: 430 * KIB },
  { label: 'HeyGen SDK vendor chunk', pattern: /^heygen-sdk-.*\.js$/, maxBytes: 450 * KIB },
]

const toKiB = (bytes) => (bytes / KIB).toFixed(2)

const assetsDir = path.resolve(process.cwd(), 'dist', 'assets')
if (!fs.existsSync(assetsDir)) {
  console.error('Bundle budget check failed: dist/assets not found. Run a production build first.')
  process.exit(1)
}

const allAssetFiles = fs.readdirSync(assetsDir)
const jsFiles = allAssetFiles.filter((file) => file.endsWith('.js'))

const violations = []
const missing = []
const rows = []

for (const budget of budgets) {
  const matches = jsFiles.filter((file) => budget.pattern.test(file))
  if (matches.length === 0) {
    missing.push(`${budget.label} (${budget.pattern})`)
    continue
  }

  const largest = matches
    .map((file) => {
      const absolutePath = path.join(assetsDir, file)
      const size = fs.statSync(absolutePath).size
      return { file, size }
    })
    .sort((a, b) => b.size - a.size)[0]

  rows.push({
    label: budget.label,
    file: largest.file,
    actualKiB: toKiB(largest.size),
    budgetKiB: toKiB(budget.maxBytes),
  })

  if (largest.size > budget.maxBytes) {
    violations.push(
      `${budget.label}: ${largest.file} is ${toKiB(largest.size)} KiB (limit ${toKiB(
        budget.maxBytes
      )} KiB)`
    )
  }
}

if (rows.length > 0) {
  console.log('Bundle budget summary:')
  console.table(rows)
}

if (missing.length > 0) {
  console.warn('Budget targets not found:')
  for (const item of missing) {
    console.warn(`- ${item}`)
  }
}

if (violations.length > 0) {
  console.error('Bundle budget violations:')
  for (const violation of violations) {
    console.error(`- ${violation}`)
  }
  process.exit(1)
}

console.log('Bundle budgets passed.')
