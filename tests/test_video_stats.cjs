const assert=require('node:assert/strict');
const test=require('node:test');
const stats=require('../web/video-player.js');
const base={id:'inbound1',timestamp:1000,framesDecoded:100,bytesReceived:10000,
 jitterBufferDelay:10,jitterBufferEmittedCount:100,totalDecodeTime:1,
 jitterBufferTargetDelay:12,framesDropped:3,packetsLost:5,freezeCount:1,totalFreezesDuration:2};
const next={...base,timestamp:2000,framesDecoded:130,bytesReceived:135000,
 jitterBufferDelay:11.5,jitterBufferEmittedCount:130,totalDecodeTime:1.03,
 jitterBufferTargetDelay:13.8,framesDropped:4,packetsLost:4,freezeCount:2,totalFreezesDuration:2.5,jitter:.002};
test('measure intervals, not lifetime averages; retain late packet correction',()=>{
 const s=stats.interval(next,base);
 assert.equal(s.fps,30);assert.equal(s.kbps,1000);assert.equal(s.buffer_ms,50);
 assert.ok(Math.abs(s.decode_ms-1)<1e-9);assert.equal(s.lost,-1);assert.equal(s.freezes,1);
 assert.equal(s.freeze_seconds,.5);assert.equal(s.jitter_ms,2);
});
test('missing counters stay unknown; zero frames do not divide by zero',()=>{
 const s=stats.interval({...base,timestamp:2000},base);
 assert.equal(s.fps,0);assert.equal(s.buffer_ms,null);assert.equal(s.decode_ms,null);
 const missing=stats.interval({id:'i',timestamp:2},{id:'i',timestamp:1});
 assert.equal(missing.fps,null);assert.equal(missing.buffer_ms,null);assert.equal(missing.freezes,null);
});
test('reconnect and counter resets never produce misleading latency',()=>{
 assert.equal(stats.interval(next,null),null);
 assert.equal(stats.interval({...next,id:'inbound2'},base),null);
 assert.equal(stats.interval({...next,framesDecoded:1},base),null);
 assert.equal(stats.interval({...next,timestamp:base.timestamp},base),null);
});
test('summary uses nearest rank, omits missing values, preserves zero',()=>{
 assert.deepEqual(stats.distribution([null,undefined,NaN]),null);
 assert.deepEqual(stats.distribution([0,1,2,3,100]),{count:5,median:2,p95:100,p99:100,max:100});
 const s=stats.summarize([stats.interval(next,base)]);
 assert.equal(s.seconds,1);assert.equal(s.freezes,1);assert.equal(s.rtt_ms,null);
 assert.equal(s.buffer_ms.median,50);
});
