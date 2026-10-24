// Neutral execution guidance shared by professional and isolated native roles.
// Tool publication, admission and evidence checks retain their own contracts.
export function configureExecutionGuidance(pi) {
  pi.on("before_agent_start", async (event, context) => ({
    systemPrompt: event.systemPrompt + "\n\nExecution organization: " +
      "Choose the next action from the user's goal and observed results. " +
      "Request independent actions in the same model response so the executor can run them concurrently. " +
      "Keep dependent actions, shared-file writes and state revision updates in order; batch order does not guarantee completion order. " +
      "When an authorized tool can carry out a known sequence of deterministic operations, complete the sequence in one action. " +
      "Preserve failure status when batching; a later successful operation must not hide a failed prerequisite. " +
      "Use another model round when an observation changes the next decision, rather than between known program steps. " +
      "Inspect source structure and available capabilities once and reuse saved results; avoid repeatedly probing the same state. " +
      "Group related validation checks and return a concise result. After a local fix, recheck affected outputs. " +
      "Finish when the requested output is usable and material checks pass; do not add optional work or repeated polishing. " +
      "This guidance does not grant tools or access. Use only published authorized tools, preserve cancellation and evidence requirements, " +
      "and report unresolved failures and limitations accurately. It does not require extra planning or progress-only model rounds." +
      (Array.isArray(context?.model?.input) && !context.model.input.includes("image")
        ? "\n\nCurrent model capability: the current model cannot inspect image content. " +
          "A successful image-file read does not provide visual understanding. Prefer authorized source data, " +
          "tables, specifications and generating code for semantic checks; reuse available supporting files. " +
          "Do not substitute pixel statistics for semantic verification of labels, series or conclusions. " +
          "Programmatic image checks may answer explicit limited questions; keep unavailable visual checks clear."
        : ""),
  }));
}

export default configureExecutionGuidance;
