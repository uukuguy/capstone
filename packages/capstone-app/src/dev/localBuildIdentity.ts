import { execFileSync } from 'node:child_process'

// Runtime sources and build inputs define the product. Local-only Vite metadata
// tooling, tests, documentation and recovery records do not define that version.
const productPaths = [
  ':(glob)packages/*/src/**',
  ...['package.json', 'package-lock.json', 'pyproject.toml', 'uv.lock', 'Dockerfile', 'Caddyfile', 'tsconfig.json']
    .map(name => `:(glob)packages/*/${name}`),
  'configs', 'schemas', 'scripts', 'Dockerfile', 'compose.yaml',
  ...['py', 'sh', 'json', 'yaml', 'yml', 'toml'].map(extension => `:(glob)deploy/**/*.${extension}`),
  ':(exclude,glob)packages/capstone-app/src/dev/**',
  ':(exclude,glob)**/*.test.*',
  ':(exclude,glob)**/__tests__/**',
]

export function localBuildIdentity(root: string) {
  const git = (...args: string[]) => execFileSync('git', args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  return {
    revision: git('log', '-1', '--format=%H', '--', ...productPaths),
    repositoryRevision: git('rev-parse', 'HEAD'),
    dirty: Boolean(git('status', '--porcelain', '--untracked-files=normal', '--', ...productPaths)),
  }
}
