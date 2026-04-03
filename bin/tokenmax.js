#!/usr/bin/env node

const { runCli } = require("../src/tokenmax/cli");

runCli(process.argv.slice(2)).catch((error) => {
  const message = error && error.message ? error.message : String(error);
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
