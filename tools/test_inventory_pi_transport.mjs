#!/usr/bin/env node

import { readFile } from "node:fs/promises";

import { createDomainToolsExtension } from "../packages/pi-capability-tools/src/domain-tools.mjs";


const descriptorPath = process.argv[2];
if (!descriptorPath) {
  throw new Error("usage: test_inventory_pi_transport.mjs DESCRIPTOR.json");
}

const descriptor = JSON.parse(await readFile(descriptorPath, "utf8"));
const registered = [];
createDomainToolsExtension(descriptor)({
  registerTool(tool) {
    registered.push(tool);
  },
});

const byName = new Map(registered.map((tool) => [tool.name, tool]));
const execute = async (name, arguments_) => {
  const tool = byName.get(name);
  if (!tool) {
    throw new Error(`inventory tool was not registered: ${name}`);
  }
  const outcome = await tool.execute(`call-${name}`, arguments_);
  if (outcome.isError) {
    throw new Error(`inventory tool failed: ${name}: ${JSON.stringify(outcome.details)}`);
  }
  return outcome.details.result;
};

const opened = await execute("inventory_catalog_open", { catalog_id: "warehouse-a" });
const listed = await execute("inventory_asset_list", {
  context_ref: opened.context_ref,
  limit: 1,
});
const summary = await execute("inventory_stock_summary", {
  context_ref: opened.context_ref,
});

process.stdout.write(`${JSON.stringify({
  registered_names: registered.map((tool) => tool.name).sort(),
  asset_count: listed.count,
  stock_asset_count: summary.asset_count,
  evidence_count: listed.evidence_refs.length + summary.evidence_refs.length,
  used_grid_wrapper: false,
})}\n`);
