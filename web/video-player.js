'use strict';
/* Browser receive-stage measurements. These never represent glass-to-glass latency. */
const AscentVideoStats = (() => {
 const valid = Number.isFinite;
 function delta(now, before, key) {
  return valid(now[key]) && valid(before[key]) ? now[key] - before[key] : null;
 }
 function interval(now, before) {
  if (!before || now.id !== before.id || now.timestamp <= before.timestamp) return null;
  const seconds = (now.timestamp - before.timestamp) / 1000;
  const frames = delta(now,before,'framesDecoded'), emitted = delta(now,before,'jitterBufferEmittedCount');
  if (frames < 0 || emitted < 0) return null;
  const average = (key,count) => {
   const value=delta(now,before,key);
   return valid(value)&&value>=0&&count>0 ? 1000*value/count : null;
  };
  const rate = key => {const value=delta(now,before,key);return valid(value)&&value>=0?value/seconds:null;};
  return {seconds, fps:rate('framesDecoded'), kbps:rate('bytesReceived')===null?null:rate('bytesReceived')*.008,
   buffer_ms:average('jitterBufferDelay',emitted), target_ms:average('jitterBufferTargetDelay',emitted),
   decode_ms:average('totalDecodeTime',frames), jitter_ms:valid(now.jitter)?now.jitter*1000:null,
   dropped:delta(now,before,'framesDropped'), lost:delta(now,before,'packetsLost'),
   freezes:delta(now,before,'freezeCount'), freeze_seconds:delta(now,before,'totalFreezesDuration'),
   width:now.frameWidth||null, height:now.frameHeight||null};
 }
 function distribution(values) {
  const sorted=values.filter(valid).sort((a,b)=>a-b);
  if (!sorted.length) return null;
  const q=p=>sorted[Math.max(0,Math.ceil(p*sorted.length)-1)];
  return {count:sorted.length,median:q(.5),p95:q(.95),p99:q(.99),max:sorted.at(-1)};
 }
 function summarize(samples) {
  const result={samples:samples.length,seconds:samples.reduce((a,s)=>a+s.seconds,0)};
  for(const key of ['fps','kbps','buffer_ms','target_ms','decode_ms','jitter_ms','rtt_ms','presentation_gap_ms'])
   result[key]=distribution(samples.map(s=>s[key]));
  for(const key of ['dropped','lost','freezes','freeze_seconds']) {
   const values=samples.map(s=>s[key]).filter(valid);
   result[key]=values.length?values.reduce((a,b)=>a+b,0):null;
  }
  return result;
 }
 return {interval,distribution,summarize};
})();
if(typeof module!=='undefined')module.exports=AscentVideoStats;

class AscentVideoPlayer {
 constructor(container,url,{mode='auto',onSample=()=>{},onStatus=()=>{}}={}) {
  this.closed=false;this.previous=null;this.receiver=null;this.onSample=onSample;this.onStatus=onStatus;
  this.mode=mode;this.lastFrame=null;this.gap=0;this.frameCallback=null;this.hasFrameCallback=false;
  this.video=document.createElement('video');
  Object.assign(this.video,{autoplay:true,muted:true,playsInline:true,disablePictureInPicture:true});
  this.video.setAttribute('aria-label','Live FPV video');container.replaceChildren(this.video);
  if(this.video.requestVideoFrameCallback) {
   this.hasFrameCallback=true;
   const presented=now=>{
    if(this.closed)return;
    if(this.lastFrame!==null)this.gap=Math.max(this.gap,now-this.lastFrame);
    this.lastFrame=now;this.frameCallback=this.video.requestVideoFrameCallback(presented);
   };
   this.frameCallback=this.video.requestVideoFrameCallback(presented);
  }
  this.onStatus('CONNECTING');
  this.reader=new MediaMTXWebRTCReader({url,
   onError:message=>{
    if(this.closed)return;
    this.receiver=null;this.previous=null;this.lastFrame=null;this.video.srcObject=null;
    this.onStatus('RECONNECTING',message);
   },
   onTrack:event=>{
    if(this.closed||event.track.kind!=='video')return;
    this.previous=null;this.receiver=event.receiver;this.lastFrame=null;this.gap=0;
    this.targetSupported='jitterBufferTarget' in event.receiver;
    if(this.targetSupported) {
     try{event.receiver.jitterBufferTarget=this.mode==='minimum'?0:null;}
     catch{this.targetSupported=false;}
    }
    this.video.srcObject=event.streams[0]||new MediaStream([event.track]);
    this.video.play().catch(()=>{if(!this.closed)this.onStatus('PRESS RECONNECT','Browser blocked autoplay');});
   }
  });
  this.timer=setTimeout(()=>this.sample(),1000);
 }
 async sample() {
  if(this.closed)return;
  try {
   if(this.receiver) {
    const receiver=this.receiver,report=await receiver.getStats();
    if(this.closed||receiver!==this.receiver)return;
    const now=[...report.values()].find(s=>s.type==='inbound-rtp'&&(s.kind||s.mediaType)==='video');
    if(now) {
     const sample=AscentVideoStats.interval(now,this.previous);this.previous=now;
     if(sample) {
      const transport=report.get(now.transportId), pair=report.get(transport?.selectedCandidatePairId);
      const candidate=report.get(pair?.localCandidateId);
      sample.rtt_ms=Number.isFinite(pair?.currentRoundTripTime)?1000*pair.currentRoundTripTime:null;
      sample.protocol=candidate?.protocol||null;
      sample.presentation_gap_ms=this.hasFrameCallback?Math.max(this.gap,this.lastFrame===null?0:performance.now()-this.lastFrame):null;
      sample.visible=!document.hidden;sample.buffer_mode=this.mode;sample.target_supported=!!this.targetSupported;
      sample.time=new Date().toISOString();this.gap=0;
      this.onSample(sample);
      this.onStatus(sample.fps>0?'PLAYING':'NO NEW FRAMES');
     }
    }
   }
  } catch(error) {if(!this.closed)this.onStatus('STATS UNAVAILABLE',error.message);}
  finally {if(!this.closed)this.timer=setTimeout(()=>this.sample(),1000);}
 }
 close() {
  this.closed=true;clearTimeout(this.timer);this.reader.close();
  if(this.frameCallback!==null)this.video.cancelVideoFrameCallback(this.frameCallback);
  this.video.pause();this.video.srcObject=null;this.video.remove();
 }
}
