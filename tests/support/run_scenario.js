// Runs one frontend scenario against the minimal DOM and prints its `out` object as JSON.
// Usage: node tests/support/run_scenario.js <repo root> <scenario body>
// The scenario body is an async function body with `browser`, `settle` and `out` in scope.
'use strict';
const {Browser, settle} = require('./minidom');
const [root, body] = process.argv.slice(2);
const out = {};
const scenario = new Function('browser', 'settle', 'out', `return (async () => {${body}})();`);
scenario(new Browser(root), settle, out)
  .then(() => settle())
  .then(() => process.stdout.write(JSON.stringify(out)))
  .catch(error => { process.stderr.write(String(error && error.stack || error)); process.exit(1); });
