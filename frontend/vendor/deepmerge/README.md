# Temporary security patch: deepmerge 4.3.1

Source: `deepmerge@4.3.1/dist/cjs.js` from the npm registry (upstream
https://github.com/TehShrike/deepmerge), with its original MIT license retained.

GHSA-gcqx-w48m-w2h4 has no upstream fixed release as of 2026-11-02. All three
assignments to `destination[key]` now use `Object.defineProperty`, creating an
enumerable, configurable, writable own property without invoking `__proto__`
setters. This also protects cloning a malicious target, not just merging a source.
The original merge, array, symbol and custom-merge behavior is otherwise retained.

This private local package is used only by Rollup's node resolver during the PWA
build. It is not an official patched upstream release. npm audit does not assess
local package source; `tests/build-security.test.cjs` exercises the patch itself.
Replace it with an upstream fix once available and validated. Do not downgrade to
an older unpatched version just to fall outside the advisory's version range.
