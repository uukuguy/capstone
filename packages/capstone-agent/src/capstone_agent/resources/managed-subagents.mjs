import {runManagedSession} from './subagents/managed-runner.mjs';

/**
 * Host-owned child-session seam for the pinned Pi subagents runner.
 *
 * createChildSession({signal}) must return {session, close}. It must create a
 * private child with the same admitted native tool wrappers, selected resources,
 * in-memory settings and fixed modelRuntime as its parent. It owns extension
 * binding and close must emit session_shutdown and dispose. No caller-controlled
 * tools, models, paths, extensions, auth or implicit history are accepted here.
 *
 * This adapter does not schedule, retry, persist ledger state or confer grants.
 * The existing host owns concurrency, parent/child identity and public receipts.
 */
export function createManagedSubagents({createChildSession, maxTurns, graceTurns = 5}) {
  if (typeof createChildSession !== 'function') throw new TypeError('createChildSession is required');
  for (const [name, value] of [['maxTurns', maxTurns], ['graceTurns', graceTurns]]) {
    if (value !== undefined && (!Number.isSafeInteger(value) || value < 1)) {
      throw new TypeError(name + ' must be a positive safe integer');
    }
  }
  return Object.freeze({
    async run({prompt, signal, onToolActivity, onTextDelta, onAssistantUsage, onModelStart, onModelResponse, onTurnEnd,
      onCompaction, onResult, settledContinuation, workDeadline}) {
      if (typeof prompt !== 'string' || !prompt.trim()) throw new TypeError('prompt is required');
      if(workDeadline&&(!Number.isFinite(workDeadline.wrapup_at_ms)||!Number.isFinite(workDeadline.finish_by_ms)||
        workDeadline.wrapup_at_ms>workDeadline.finish_by_ms))throw new TypeError('Invalid absolute child work window');
      if(workDeadline&&Date.now()>=workDeadline.finish_by_ms){
        const result=Object.freeze({responseText:'',aborted:true,steered:false,budget_exhausted:true,turns:0,modelResponses:0,usage:Object.freeze([])});
        await onResult?.(result);return result;
      }
      if (signal?.aborted) {
        const result = Object.freeze({responseText: '', aborted: true, steered: false, turns: 0, modelResponses: 0, usage: Object.freeze([])});
        await onResult?.(result);
        return result;
      }
      const owned = await createChildSession({signal});
      // The trusted factory is responsible for cleaning partial construction if
      // it throws; every successfully returned handle must include close.
      if (!owned || typeof owned.close !== 'function') throw new TypeError('child close is required');
      const {session} = owned;
      let abortPromise;
      let abortError;
      const abort = () => {
        if (!abortPromise) {
          abortPromise = Promise.resolve().then(() => session.abort()).catch(error => { abortError = error; });
        }
      };
      let result;
      let failure;
      let failed = false;
      try {
        for (const method of ['prompt', 'subscribe', 'abort', 'steer']) {
          if (typeof session?.[method] !== 'function') throw new TypeError('invalid child session');
        }
        if (!Array.isArray(session.messages)) throw new TypeError('invalid child messages');
        signal?.addEventListener('abort', abort, {once: true});
        if (signal?.aborted) abort();
        result = await runManagedSession(session, prompt, {signal, abort, maxTurns, graceTurns,
          onToolActivity, onTextDelta, onAssistantUsage, onModelStart, onModelResponse, onTurnEnd, onCompaction, settledContinuation,workDeadline});
      } catch (error) {
        failed = true;
        failure = error;
        abort();
      } finally {
        signal?.removeEventListener('abort', abort);
        if (abortPromise) await abortPromise;
        try { await owned.close(); } catch (error) {
          if (!failed) { failed = true; failure = error; }
        }
      }
      if (failed) throw failure;
      if (abortError) throw abortError;
      result = Object.freeze(result);
      await onResult?.(result);
      return result;
    },
  });
}
