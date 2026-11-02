import { execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, expect, it } from 'vitest'
import { localBuildIdentity } from './localBuildIdentity'

const roots: string[] = []
function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'capstone-version-')); roots.push(root)
  const git = (...args: string[]) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim()
  git('init', '-q'); git('config', 'user.name', 'Version test'); git('config', 'user.email', 'version@example.invalid')
  const write = (path: string, value: string) => { mkdirSync(join(root, path, '..'), { recursive: true }); writeFileSync(join(root, path), value) }
  const commit = () => { git('add', '.'); git('commit', '-qm', 'fixture'); return git('rev-parse', 'HEAD') }
  write('packages/capstone-app/src/main.tsx', 'product'); const revision = commit()
  return { root, write, commit, revision }
}
afterEach(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true }) })

it('keeps product identity across documentation and local metadata changes', () => {
  const f = fixture()
  f.write('docs/report.md', 'receipt'); f.write('deploy/railway/README.md', 'procedure')
  f.write('packages/capstone-app/vite.config.ts', 'local metadata'); const repositoryRevision = f.commit()
  expect(localBuildIdentity(f.root)).toEqual({ revision: f.revision, repositoryRevision, dirty: false })
  f.write('docs/report.md', 'updated'); f.write('deploy/railway/README.md', 'updated')
  expect(localBuildIdentity(f.root).dirty).toBe(false)
})

it('marks uncommitted runtime changes and advances after committing them', () => {
  const f = fixture(); f.write('packages/capstone-app/src/main.tsx', 'changed')
  expect(localBuildIdentity(f.root)).toMatchObject({ revision: f.revision, dirty: true })
  const revision = f.commit(); expect(localBuildIdentity(f.root)).toEqual({ revision, repositoryRevision: revision, dirty: false })
})

it('includes domain guides, dependency pins and deployment code', () => {
  for (const path of ['packages/domain/src/policy.md', 'packages/domain/uv.lock', 'deploy/launch.py', 'Dockerfile']) {
    const f = fixture(); f.write(path, 'runtime')
    expect(localBuildIdentity(f.root).dirty).toBe(true)
    const revision = f.commit(); expect(localBuildIdentity(f.root).revision).toBe(revision)
  }
})
