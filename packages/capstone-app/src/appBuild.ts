export type AppEnvironment = 'local-dev' | 'local-demo' | 'cloud-dev' | 'cloud-demo'
export interface AppBuildIdentity {
  version: string
  revision: string
  dirty: boolean
  environment: AppEnvironment | null
}

export function isAppBuildIdentity(value: unknown): value is AppBuildIdentity {
  if (!value || typeof value !== 'object') return false
  const build = value as Record<string, unknown>
  return typeof build.version === 'string' && typeof build.revision === 'string' &&
    (build.revision === '' || /^[a-f0-9]{40}$/.test(build.revision)) && typeof build.dirty === 'boolean' &&
    (build.environment === null || ['local-dev', 'local-demo', 'cloud-dev', 'cloud-demo'].includes(build.environment as string))
}
