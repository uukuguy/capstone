import test from 'node:test';
import assert from 'node:assert/strict';
import {sdkFailureDiagnostic} from '../../src/capstone_agent/resources/general-sdk.mjs';

test('SDK failure diagnostics retain trusted locations without error values or external paths',()=>{
  const root=new URL('../../src/capstone_agent/resources/',import.meta.url).href;
  const error=new TypeError('SECRET_ARGUMENT');
  error.stack=`TypeError: SECRET_ARGUMENT\n    at run (${root}general-sdk.mjs:42:7)\n    at x (file:///private/SECRET_PATH.js:2:1)`;
  assert.deepEqual(sdkFailureDiagnostic(error),{exception_type:'TypeError',origin:[{module:'general-sdk.mjs',line:42,column:7}]});
});
