import { spawn } from "node:child_process";
import {CapacityExceeded} from './runtime-limits.mjs';

/** Execute one already validated, fixed authority process request. */
export function runProcessCapability(payload, runtime, limits, environment) {
  return new Promise((resolveResponse,rejectResponse) => {
    const started=Date.now();
    const child = spawn(runtime.executable, runtime.executableArgs, {
      env: environment,
      stdio: ["pipe", "pipe", "pipe"],
    });
    const stdout = [];
    let stdoutBytes = 0;
    let stderrBytes = 0;
    let settled = false;
    const finish = (response) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      resolveResponse(response);
    };
    const stopWithError = (code, message,capacity={}) => {
      if(settled)return;
      child.kill("SIGKILL");
      if(limits.runtimeLimitMode==='debug'&&capacity.dimension){
        settled=true;clearTimeout(timer);
        rejectResponse(new CapacityExceeded({[capacity.dimension]:capacity.limit},capacity.dimension,
          capacity.actual,capacity.unit,'execute',{mode:'debug'}));
        return;
      }
      const response=transportError(payload.request_id, runtime, message, code);
      response.error={...response.error,...capacity};
      finish(response);
    };
    const timer = setTimeout(() => {
      stopWithError(
        "capability_transport_timeout",
        `capability executable exceeded ${limits.timeoutMs}ms transport timeout`,
        {dimension:'tool_timeout_seconds',actual:(Date.now()-started)/1000,limit:limits.timeoutMs/1000,unit:'seconds',retryable:false},
      );
    }, limits.timeoutMs);
    child.stdout.on("data", (chunk) => {
      const buffer = Buffer.from(chunk);
      stdoutBytes += buffer.byteLength;
      if (stdoutBytes + stderrBytes > limits.maxOutputBytes) {
        stopWithError(
          "capability_transport_output_limit",
          `capability executable exceeded ${limits.maxOutputBytes} transport output bytes`,
          {dimension:'tool_observation_bytes',actual:stdoutBytes+stderrBytes,limit:limits.maxOutputBytes,unit:'bytes',retryable:false},
        );
        return;
      }
      stdout.push(buffer);
    });
    child.stderr.on("data", (chunk) => {
      const buffer = Buffer.from(chunk);
      stderrBytes += buffer.byteLength;
      if (stdoutBytes + stderrBytes > limits.maxOutputBytes) {
        stopWithError(
          "capability_transport_output_limit",
          `capability executable exceeded ${limits.maxOutputBytes} transport output bytes`,
          {dimension:'tool_observation_bytes',actual:stdoutBytes+stderrBytes,limit:limits.maxOutputBytes,unit:'bytes',retryable:false},
        );
      }
    });
    child.on("error", () => {
      finish(transportError(payload.request_id, runtime, "capability executable could not start"));
    });
    child.on("close", (code, signal) => {
      if (settled) {
        return;
      }
      const stdoutText = Buffer.concat(stdout).toString("utf8");
      try {
        const response = JSON.parse(stdoutText);
        if (code !== 0 || signal !== null) {
          if (isCorrelatedResponse(response, payload.request_id, runtime) && response.ok === false) {
            finish(response);
          } else {
            finish(transportError(
              payload.request_id,
              runtime,
              "capability executable exited unsuccessfully",
              "capability_transport_process_failed",
            ));
          }
          return;
        }
        finish(response);
      } catch {
        finish(
          transportError(
            payload.request_id,
            runtime,
            "capability executable returned invalid JSON",
          ),
        );
      }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

export function isCorrelatedResponse(response, requestId, descriptor) {
  return (
    response &&
    response.protocol === descriptor.protocol &&
    response.protocol_version === descriptor.protocolVersion &&
    response.request_id === requestId
  );
}

function transportError(
  requestId,
  descriptor,
  message,
  code = "capability_transport_error",
) {
  return {
    protocol: descriptor.protocol,
    protocol_version: descriptor.protocolVersion,
    request_id: requestId,
    ok: false,
    error: {
      code,
      phase: "execute",
      message,
    },
  };
}
