import {
  CanonicalRequestContractError,
  captureFatal,
  configureModelRequestCapture as configureNeutralModelRequestCapture,
} from "@capability-agent/pi-tools/model-request-capture";

const LEGACY_MODEL_REQUEST_SCHEMA_VERSION = "grid-model-request-input/2.0";

export function configureModelRequestCapture(pi, paths, fatal = captureFatal) {
  return configureNeutralModelRequestCapture(
    pi,
    { ...paths, schemaVersion: LEGACY_MODEL_REQUEST_SCHEMA_VERSION },
    fatal,
  );
}

export const configureTrajectoryCapture = configureModelRequestCapture;
export { CanonicalRequestContractError, captureFatal };
