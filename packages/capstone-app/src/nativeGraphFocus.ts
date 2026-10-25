import type {ExecutionGraph} from './executionGraph'

/** The validated host-admitted task organization determines presentation. */
export function nativeGraphFocus(graph:ExecutionGraph|undefined):'tasks'|undefined {
  return graph?'tasks':undefined
}
