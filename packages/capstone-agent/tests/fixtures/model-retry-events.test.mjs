import test from 'node:test';
import assert from 'node:assert/strict';
import {rpcEvent} from '../../src/capstone_agent/resources/general-sdk.mjs';
test('retry projection retains bounded lifecycle fields without provider error text',()=>{
 const first=rpcEvent({type:'auto_retry_start',attempt:1,maxAttempts:2,delayMs:1000,errorMessage:'network timeout PRIVATE_OUTPUT'});
 assert.deepEqual(first,{type:'auto_retry_start',attempt:1,maxAttempts:2,delayMs:1000,errorCode:'model_transport'});
 assert.ok(!JSON.stringify(first).includes('PRIVATE_OUTPUT'));
 assert.deepEqual(rpcEvent({type:'auto_retry_end',attempt:1,success:true,finalError:'PRIVATE_OUTPUT'}),{type:'auto_retry_end',attempt:1,success:true});
});
