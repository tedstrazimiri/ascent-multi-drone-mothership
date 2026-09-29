'use strict';
const $ = id => document.getElementById(id);
let state = null, hydrated = false, currentPage = 'live', mode = 'arming';
let videoEnabled = true, videoURL = '', noticeTimer, disconnected = false, pending = false;
let videoPlayer = null, videoStats = null, playerStatus = 'CONNECTING', videoMeasurement = null, measurementTimer = null;
let renderedLogs = '', renderedMapping = '', primaryActionsVisible = true;
function updateGlobalStop() {$('global-stop').hidden = !state?.session.active || (currentPage === 'live' && primaryActionsVisible);}
new IntersectionObserver(([entry]) => {primaryActionsVisible = entry.isIntersecting && entry.intersectionRatio > .8;updateGlobalStop();},{threshold:[0,.8,1]}).observe(document.querySelector('.test-actions'));
const channelNames = ['ROLL','PITCH','THR','YAW'];
const setText = (id, text) => {if ($(id).textContent !== String(text)) $(id).textContent = text;};
function notice(text, error = false) {
 clearTimeout(noticeTimer); setText('notice-text', text); $('notice').hidden = false;
 $('notice').classList.toggle('error', error);
 noticeTimer = setTimeout(() => {$('notice').hidden = true;}, error ? 15000 : 5000);
}
$('dismiss-notice').onclick = () => {$('notice').hidden = true;};
async function api(action, data = {}) {
 if (!state) throw Error('Console connecting');
 const response = await fetch('/api/' + action, {method:'POST', headers:{'Content-Type':'application/json','X-Console-Token':state.token},body:JSON.stringify(data),signal:AbortSignal.timeout(8000)});
 const result = await response.json();
 if (!response.ok) throw Error(result.error || 'Operation failed');
 return result;
}
function perform(fn) {return async () => {
 if (pending) return;
 pending = true; if (state) render(state);
 try {await fn();} catch(error) {notice(error.message, true);}
 finally {pending = false; if (state) render(state);}
};}
function page(name, updateHash = true) {
 if (name === 'arming' || name === 'bench') {mode = name === 'arming' ? 'arming' : 'joystick'; name = 'live';}
 if (!['live','controller','calibration','connections'].includes(name)) name = 'live';
 currentPage = name;
 document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + name));
 document.querySelectorAll('[data-page]').forEach(p => {p.classList.toggle('active', p.dataset.page === name); p.setAttribute('aria-current', p.dataset.page === name ? 'page' : 'false');});
 if (name !== 'live') document.body.classList.remove('expanded');
 $('expand-video').setAttribute('aria-pressed', String(document.body.classList.contains('expanded')));
 if (updateHash && location.hash !== '#' + name) history.replaceState(null, '', '#' + name);
 if (state) render(state);
 window.scrollTo({top:0});
}
document.querySelectorAll('[data-page]').forEach(b => b.onclick = () => page(b.dataset.page));
document.querySelectorAll('[data-go]').forEach(b => b.onclick = () => page(b.dataset.go));
window.addEventListener('hashchange', () => page(location.hash.slice(1), false));
document.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => {if (!state?.session.active) {mode=b.dataset.mode; if(state) render(state);}});
function makeBar(name, id) {
 const row = document.createElement('div'); row.className = 'channel-row';
 row.innerHTML = `<div class="labels"><span>${name}</span><b id="${id}-value">—</b></div><div class="bar-track"><div class="bar-fill" id="${id}-fill"></div><i class="bar-marker" id="${id}-marker"></i></div>`;
 return row;
}
channelNames.forEach((n,i) => $('input-bars').append(makeBar(n,'input-'+i)));
[...channelNames,'ARM'].forEach((n,i) => $('fc-bars').append(makeBar(n,'fc-'+i)));
function bar(id, value, min, max) {
 const valid=Number.isFinite(value), fraction=valid?Math.max(0,Math.min(1,(value-min)/(max-min))):0;
 setText(id+'-value',valid?Math.round(value):'—');
 $(id+'-fill').style.width=100*fraction+'%'; $(id+'-marker').style.left=100*fraction+'%';
 $(id+'-value').closest('.channel-row').classList.toggle('no-data',!valid);
}
function moveStick(prefix,x,y) {
 for(const name of [prefix+'-stick',prefix+'-stick-halo']) {
  $(name).setAttribute('cx',(prefix==='left'?207:453)+49*x); $(name).setAttribute('cy',218-49*y);
 }
}
function status(id,ok,title) {$(id).classList.toggle('ok',!!ok);if(title)$(id).title=title;}
function fmt(v,n=1) {return Number.isFinite(v)?v.toFixed(n):'—';}
function settingsFromForm() {return {host:$('host-input').value.trim(),transport:$('transport-input').value,seconds:Number($('duration-input').value),video_bitrate:Number($('bitrate-input').value)};}
async function saveSettings(show=true) {const settings=settingsFromForm(),hostChanged=settings.host!==state.settings.host;await api('settings',settings);if(show)notice('Saved');if(hostChanged)location.reload();}
function mappingRow(label,value) {const row=document.createElement('div');row.className='mapping-row';const a=document.createElement('span'),b=document.createElement('span');a.textContent=label;b.textContent=value;row.append(a,b);return row;}
function guidance(s,selectedMode,ready) {
 const q=s.session, h=s.hid;
 if(disconnected) return ['!','CONSOLE OFFLINE','Reconnecting. Output watchdog active.','error'];
 if(s.job.busy) return ['↻','PREPARING',s.job.message,''];
 if(wizard.active) return ['◎','CALIBRATION OPEN','Finish or cancel calibration.',''];
 if(q.active) {
  if(q.state==='ready')return ['↑','SA → HIGH','Motors may spin · 2s cutoff','ready'];
  if(q.state==='live')return ['●',q.kind==='arming'?'ARM REQUESTED':'OUTPUT ACTIVE',q.kind==='arming'?'SA low / STOP → disarm':q.kind==='synthetic'?'Roll link check · ARM locked':'SA low / STOP → end','live'];
  if(q.state==='recovering')return ['↓','HOLD SA LOW','Wait for the ready cue.',''];
  if(q.state==='preparing'||q.state==='starting')return ['↻','AUTO SETUP',q.message.includes('FC')?'Checking indoor FC profile…':'Preparing relay…',''];
  if(q.state==='stopping')return ['■','STOPPING','Sending disarm frames…',''];
  const text=q.message||'';
  if(/Connect FC USB/i.test(text))return ['↗','CONNECT FC USB','Indoor profile required once.',''];
  if(/Connect the TX15/i.test(text))return ['↗','CONNECT TX15','USB joystick mode',''];
  if(/throttle/i.test(text))return ['↓','THROTTLE → MIN','Waiting · ARM held off',''];
  if(/SA.*low|SA.*off/i.test(text))return ['↓','SA → LOW','Wait for the ready cue.',''];
  return ['○','WAITING',text,''];
 }
 if(q.state==='error' && q.kind===selectedMode)return ['!','TEST STOPPED',q.message,'error'];
 if(q.kind===selectedMode && q.state==='stopped')return ['✓','TEST ENDED',selectedMode==='arming'?'SA low → Start again': 'Output stopped · ready to retry',''];
 if(selectedMode==='arming')return ['○','READY TO SET UP','Start → SA low → high',''];
 if(!ready.relay)return ['↗','PREPARE RELAY','Link → Check / Prepare',''];
 if(!ready.fc)return ['↗','CONNECT FC USB','SBUS · disarmed',''];
 if(selectedMode==='joystick') {
  if(!h.connected)return ['↗','CONNECT TX15','USB joystick mode',''];
  if(!ready.throttle)return ['↓','THROTTLE → MIN','Lower fully before Start.',''];
  if(!h.enabled)return ['↑','SA → ENABLE','Use the calibrated switch position.',''];
 }
 return ['✓','READY',selectedMode==='synthetic'?'4s roll sweep · ARM locked':'Live sticks · ARM locked','ready'];
}
function render(s) {
 if(disconnected)s={...s,hid:{...s.hid,connected:false},fc:{connected:false,channels:[]},pi:{connected:false},video:{available:false,updated:Date.now()/1000}};
 const h=s.hid,f=s.fc,p=s.pi,q=s.session,a=s.arm_profile||{};
 if(!hydrated){$('host-input').value=s.settings.host;$('transport-input').value=s.settings.transport;$('duration-input').value=s.settings.seconds;$('bitrate-input').value=s.settings.video_bitrate;hydrated=true;}
 $('preview-banner').hidden=!s.preview;document.body.classList.toggle('is-preview',!!s.preview);
 status('console-status',!disconnected);setText('console-status',disconnected?'OFFLINE':'LOCAL');
 status('radio-badge',h.connected,h.connected?'TX15 USB connected':'TX15 USB offline');
 status('link-badge',p.connected,p.connected?'Last check: '+(p.host||s.settings.host):'Relay not checked');
 status('profile-indicator',a.ready,a.message);setText('profile-indicator',a.ready?'INDOOR READY':'AUTO SETUP');
 $('radio-stage').classList.toggle('disconnected',!h.connected);
 setText('hid-detail',h.connected?'USB CONNECTED':'USB OFFLINE');setText('radio-lcd',h.connected?'USB CONNECTED':'CONNECT USB');
 setText('radio-lock',q.active&&q.kind==='arming'?'ARM TEST / IDLE ONLY':'PREVIEW / NO OUTPUT');
 const normal=(h.channels||[]).map(v=>2*(v-172)/1639-1);
 moveStick('left',h.connected?normal[3]||0:0,h.connected&&Number.isFinite(normal[2])?normal[2]:-1);
 moveStick('right',h.connected?normal[0]||0:0,h.connected?normal[1]||0:0);
 channelNames.forEach((n,i)=>bar('input-'+i,h.connected?1000+(h.channels[i]-172)*1000/1639:null,1000,2000));
 const gate=s.mapping.deadman_axis,sa=h.connected&&gate?h.axes[gate.index]:undefined;
 const pos=Number.isFinite(sa)?(sa<-12000?0:sa>12000?2:1):-1;
 document.querySelectorAll('#sa-positions>div').forEach(el=>{el.classList.toggle('selected',Number(el.dataset.position)===pos);el.setAttribute('aria-label',['SA low','SA middle','SA high'][el.dataset.position]+(Number(el.dataset.position)===pos?' selected':''));});
 setText('sa-number',pos<0?'—':['−100%','0%','+100%'][pos]);
 $('sa-lever').setAttribute('d',['M160 85 L145 53','M160 85 L160 49','M160 85 L175 53'][Math.max(0,pos)]);
 const throttle=h.connected&&Number.isFinite(h.channels[2])?Math.max(0,Math.min(100,(h.channels[2]-172)*100/1639)):null;
 setText('throttle-value',throttle===null?'—':throttle<=2.4?'MIN':Math.round(throttle)+'%');$('throttle-fill').style.width=(throttle||0)+'%';
 setText('fc-battery',f.connected?fmt(f.voltage,2)+' V':'—');
 setText('fc-armed',f.connected?(f.armed?'ARMED':'DISARMED'):'UNKNOWN');$('fc-armed').style.color=f.connected?(f.armed?'var(--red)':'var(--green)'):'var(--muted)';
 setText('fc-badge',f.connected?'USB READBACK':'USB OFFLINE');
 setText('fc-detail',f.connected?`TAKER H743 / ${f.sbus?'SBUS':'CHECK RX'} / ${f.cells||'?'}S`:'USB offline · connect TAKER H743');
 setText('arm-fc-status',f.connected?((f.arming_blockers||[]).length?'FC: '+f.arming_blockers.join(' · '):'FC disarmed · no blockers'):'FC USB offline · armed state unknown');
 if(f.connected&&f.armed)setText('arm-fc-status','FC REPORTS ARMED');
 [0,1,3,2,4].forEach((source,i)=>bar('fc-'+i,f.connected?f.channels[source]:null,987,2011));
 const age=p.updated?Math.max(0,Date.now()/1000-p.updated):null;
 setText('ping-value',p.connected&&Number.isFinite(p.ping_ms)?fmt(p.ping_ms)+' ms':'—');setText('rtt-age',p.connected&&age>60?'LAST':'');
 $('ping-value').title=age!==null?'Measured '+Math.round(age)+' seconds ago; not video latency':'Check link to measure';
 setText('pi-state',p.connected?'CONNECTED':p.checking?'CHECKING':'UNCHECKED');
 setText('video-state',p.connected?(p.video==='active'&&p.media==='active'?'RUNNING':'CHECK SERVICES'):'—');
 setText('receiver-state',p.connected?(p.receiver&&p.driver&&p.key?'PREPARED':'PREPARE RELAY'):'—');
 setText('pi-detail',p.error||(p.connected?p.hostname+' / '+s.settings.host:'Check the relay to measure round-trip time.'));
 for(const [id,ok] of [['path-radio',h.connected],['path-pi',p.connected],['path-fc',f.connected]])$(id).classList.toggle('ok',!!ok);
 setText('toggle-fc',s.fc_enabled?'Release FC USB':'Connect FC USB');setText('arm-profile-state',a.message||'Start prepares the profile automatically.');
 const ready={relay:p.connected&&p.receiver&&p.driver&&p.key,fc:f.connected&&f.sbus&&!f.armed,throttle:h.connected&&h.channels[2]<=210};
 const selectedMode=q.active?q.kind:mode,locked=q.active||s.job.busy||pending||disconnected;
 document.querySelectorAll('[data-mode]').forEach(el=>{el.classList.toggle('selected',el.dataset.mode===selectedMode);el.setAttribute('aria-pressed',String(el.dataset.mode===selectedMode));el.disabled=q.active||pending;});
 setText('mode-caption',selectedMode==='arming'?'PROPS OFF · IDLE ONLY':'PROPS OFF · ARM LOCKED');
 setText('test-limit',selectedMode==='arming'?'2s MAX':selectedMode==='synthetic'?'4s':s.settings.seconds+'s');
 const good=selectedMode==='arming'||(ready.relay&&ready.fc&&(selectedMode==='synthetic'||h.connected&&h.enabled&&ready.throttle));
 $('start-test').disabled=locked||wizard.active||!good;
 setText('start-label',q.active?'Running…':q.kind===selectedMode?'Start again':selectedMode==='arming'?'Start arm test':'Start test');
 // Stop stays available even while another request or a reconnection is pending.
 $('stop-test').disabled=!q.active;$('stop-global').disabled=!q.active;
 for(const id of ['check-pi','prepare-pi','save-connection','save-video','apply-bitrate','restart-video','toggle-fc','wizard-start','duration-input','host-input','transport-input','bitrate-input'])$(id).disabled=locked;
 $('prepare-arm').disabled=locked||!f.connected||f.armed;$('restore-arm').disabled=locked||!f.connected||f.armed||!a.ready;
 const g=guidance(s,selectedMode,ready);setText('guidance-symbol',g[0]);setText('test-title',g[1]);setText('test-detail',g[2]);$('test-guidance').className='test-guidance '+g[3];$('test-guidance').title=q.active?q.message:'';
 setText('frame-count',q.frames||0);setText('session-state',q.active?(q.state==='live'?'OUTPUT ACTIVE':q.frames?'ARM HELD LOW':'SETUP / OUTPUT OFF'):'OUTPUT OFF');
 setText('session-clock',q.active?(q.kind==='arming'?'WINDOW ':'')+Math.max(0,Math.ceil(q.seconds-(Date.now()/1000-q.started)))+'s':'—');
 document.querySelector('.session-meter').classList.toggle('active',q.active);updateGlobalStop();
 setText('global-stop-label',q.kind==='arming'?'ARM TEST ACTIVE':'TEST ACTIVE');
 const mappingKey=JSON.stringify(s.mapping);
 if(mappingKey!==renderedMapping){renderedMapping=mappingKey;$('mapping-list').replaceChildren(...s.mapping.axes.map((ax,i)=>mappingRow(channelNames[i],`AX${ax.index} ${ax.invert?'REV':'NOR'}`)),mappingRow('SA',gate?`AX${gate.index} ${gate.min>0?'HIGH':gate.max<0?'LOW':'CUSTOM'}`:'BUTTON'));}
 const latest=s.logs.at(-1);setText('activity-latest',s.job.busy?s.job.message:latest?.text||'SYSTEM STANDBY');
 const logKey=JSON.stringify(s.logs);if(logKey!==renderedLogs){renderedLogs=logKey;$('activity-log').replaceChildren(...s.logs.slice().reverse().map(log=>{const row=document.createElement('div');row.className='log-row '+log.level;const time=document.createElement('span'),text=document.createElement('span');time.textContent=log.time;text.textContent=log.text;row.append(time,text);return row;}));}
 syncVideo(s);
 if(wizard.active)observeCalibration(h);
}
function syncVideo(s,force=false) {
 const source=s.video||{},fresh=source.updated&&Date.now()/1000-source.updated<15;
 const available=source.available&&fresh&&!disconnected;
 setText('transport-label',s.settings.transport.toUpperCase());setText('stream-bitrate',s.settings.video_bitrate+' Mbps');
 $('toggle-video').setAttribute('aria-pressed',String(videoEnabled));$('toggle-video').setAttribute('aria-label',videoEnabled?'Pause video':'Play video');$('toggle-video').title=videoEnabled?'Pause video':'Play video';
 setText('feed-status',videoEnabled?(videoPlayer?playerStatus:available?'SOURCE ONLINE':'SOURCE OFFLINE'):'PAUSED');
 setText('source-label',available?'STREAM AVAILABLE':source.updated?'SOURCE UNAVAILABLE':'CHECKING SOURCE');$('source-dot').classList.toggle('ok',!!available);
 setText('video-placeholder-title',!videoEnabled?'VIDEO PAUSED':disconnected?'CONSOLE OFFLINE':source.updated?'NO VIDEO LINK':'CONNECTING');
 setText('video-placeholder-detail',!videoEnabled?'PRESS POWER TO RESUME':s.settings.host+' / FPV 01');
 // WebRTC owns its connection lifecycle. A failed HLS probe must not tear down healthy video.
 const canPlay=!disconnected&&(s.settings.transport==='webrtc'||available);
 const url=videoEnabled&&canPlay&&currentPage==='live'?(s.preview?'/preview-feed':`http://${s.settings.host}:${s.settings.transport==='hls'?8888:8889}/fpv1/`):'';
 if(url!==videoURL||force){
  if(videoMeasurement?.running)finishVideoMeasurement('Interrupted: player changed or source became unavailable');
  videoPlayer?.close();videoPlayer=null;videoStats=null;playerStatus='CONNECTING';videoURL=url;$('video-frame').replaceChildren();
  for(const id of ['timing-fps','timing-buffer','timing-decode','timing-rtt'])setText(id,'—');
  setText('stream-config','1280 × 720 / configured 30 FPS');$('stream-config').title='Configured capture format; not a measured frame rate';
  if(url){
   if(!s.preview&&s.settings.transport==='webrtc')videoPlayer=new AscentVideoPlayer($('video-frame'),url+'whep',{
    mode:$('buffer-mode').value,onSample:sample=>updateVideoStats(sample),
    onStatus:(status,detail)=>{playerStatus=status;$('feed-status').title=detail||status;if(status==='RECONNECTING'){videoStats=null;for(const id of ['timing-fps','timing-buffer','timing-decode','timing-rtt'])setText(id,'—');setText('stream-config','Waiting for decoded frames');finishVideoMeasurement('Interrupted: WebRTC disconnected');}}
   });
   else{const frame=document.createElement('iframe');frame.title='FPV 01 video player';frame.src=url;frame.allow='autoplay; fullscreen';$('video-frame').append(frame);}
  }
 }
 $('measure-video').disabled=!videoPlayer||!videoStats||videoMeasurement?.running;
 $('buffer-mode').disabled=!videoPlayer||videoMeasurement?.running;
 setText('timing-status',videoPlayer?(videoStats?'Receiving · '+(videoStats.protocol||'transport unknown').toUpperCase():playerStatus):'Select WebRTC for measurements');
 $('video-placeholder').hidden=!!url;
 $('video-stall').hidden=!videoPlayer||playerStatus==='PLAYING';setText('video-stall',playerStatus);
}
function updateVideoStats(sample) {
 videoStats=sample;
 setText('timing-fps',fmt(sample.fps)+' fps');setText('timing-buffer',fmt(sample.buffer_ms)+' ms');
 setText('timing-decode',fmt(sample.decode_ms)+' ms');setText('timing-rtt',fmt(sample.rtt_ms)+' ms');
 if(sample.width&&sample.height)setText('stream-config',`${sample.width} × ${sample.height} / ${fmt(sample.fps)} FPS`);
 $('stream-config').title='Decoded frame rate over the last sampling interval';
 $('buffer-mode').title=sample.target_supported?'Browser supports requested buffer target':'Buffer target unsupported; browser automatic behavior';
 if(videoMeasurement?.running){
  videoMeasurement.samples.push(sample);
  setText('timing-summary',`Recording · ${Math.min(30,Math.floor((performance.now()-videoMeasurement.start)/1000))} / 30 seconds`);
 }
}
function finishVideoMeasurement(reason='Complete') {
 clearTimeout(measurementTimer);
 if(!videoMeasurement?.running)return;
 videoMeasurement.running=false;videoMeasurement.result=reason;
 videoMeasurement.summary=AscentVideoStats.summarize(videoMeasurement.samples);
 videoMeasurement.elapsed_seconds=(performance.now()-videoMeasurement.start)/1000;
 const q=videoMeasurement.summary;
 const percentile=(key,p)=>fmt(q[key]?.[p]);
 setText('timing-summary',`${reason} · ${q.samples} samples / ${fmt(q.seconds)} s
Receive buffer median / p95: ${percentile('buffer_ms','median')} / ${percentile('buffer_ms','p95')} ms (${q.buffer_ms?.count??0} intervals with emitted frames)
Decode median: ${percentile('decode_ms','median')} ms · decoded FPS median: ${percentile('fps','median')}
Freezes: ${q.freezes??'unknown'} · dropped frames: ${q.dropped??'unknown'} · net packets lost: ${q.lost??'unknown'}
These are receive-stage interval statistics, not camera-to-screen delay.`);
 $('export-video').disabled=false;
}
$('buffer-mode').onchange=()=>{if(state)syncVideo(state,true);};
$('measure-video').onclick=()=>{
 if(!videoPlayer||!videoStats||videoMeasurement?.running)return;
 videoMeasurement={running:true,start:performance.now(),started:new Date().toISOString(),samples:[],host:state.settings.host,buffer_mode:$('buffer-mode').value,
  caveat:'Browser receive-stage interval statistics. Excludes camera, RF, capture and encoding. Percentiles summarize roughly one-second averages; not individual frame latency.',user_agent:navigator.userAgent};
 videoPlayer.previous=null; // Begin with a fresh counter baseline inside this measurement window.
 $('export-video').disabled=true;setText('timing-summary','Recording · keep this tab visible');
 measurementTimer=setTimeout(()=>finishVideoMeasurement(),30000);
};
$('export-video').onclick=()=>{
 if(!videoMeasurement||videoMeasurement.running)return;
 const {start,running,...report}=videoMeasurement;
 const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)+'\n'],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='ascent-video-'+report.started.replaceAll(':','-')+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&videoMeasurement?.running)finishVideoMeasurement('Interrupted: tab hidden');});
window.addEventListener('pagehide',()=>videoPlayer?.close());
async function poll() {
 try {
  const r=await fetch('/api/state',{cache:'no-store',signal:AbortSignal.timeout(2000)});if(!r.ok)throw Error('Console unavailable');
  state=await r.json();if(disconnected)$('notice').hidden=true;disconnected=false;render(state);
 } catch(error) {
  if(!disconnected)notice('Console offline. Control watchdog active. Reconnecting…',true);
  disconnected=true;
  if(state)render(state);
 }
 setTimeout(poll,150);
}
$('toggle-video').onclick=()=>{videoEnabled=!videoEnabled;if(state)syncVideo(state);};
$('reload-video').onclick=()=>{videoEnabled=true;if(state)syncVideo(state,true);};
$('expand-video').onclick=()=>{document.body.classList.toggle('expanded');$('expand-video').setAttribute('aria-pressed',String(document.body.classList.contains('expanded')));$('expand-video').setAttribute('aria-label',document.body.classList.contains('expanded')?'Restore video layout':'Expand video');};
$('toggle-log').onclick=()=>{$('activity-log').hidden=!$('activity-log').hidden;$('toggle-log').setAttribute('aria-expanded',String(!$('activity-log').hidden));if(!$('activity-log').hidden)$('activity-log').scrollIntoView({block:'nearest'});};
$('save-connection').onclick=perform(()=>saveSettings());
$('save-video').onclick=perform(()=>saveSettings());
$('check-pi').onclick=perform(async()=>{await saveSettings(false);await api('check');});
$('prepare-pi').onclick=perform(async()=>{await saveSettings(false);await api('prepare');});
$('apply-bitrate').onclick=perform(async()=>{await saveSettings(false);await api('video_bitrate');notice('Applying bitrate · stream will reconnect');});
$('restart-video').onclick=perform(async()=>{await api('video_restart');notice('Restarting stream');});
$('toggle-fc').onclick=perform(()=>api('fc',{enabled:!state.fc_enabled}));
$('prepare-arm').onclick=perform(()=>api('arm_prepare'));
$('restore-arm').onclick=perform(()=>api('arm_restore'));
$('start-test').onclick=perform(async()=>{if(wizard.active)return;await api('start',{kind:mode});});
const stop=async()=>{try{await api('stop');}catch(e){notice('Stop not acknowledged. Link-loss watchdog remains active.',true);}};
$('stop-test').onclick=stop;$('stop-global').onclick=stop;
$('duration-input').onchange=perform(()=>saveSettings(false));

const steps=[
 {name:'Roll',symbol:'↔',slot:0,title:'Roll / right stick',instruction:'Right → left → centre. Keep other controls still.'},
 {name:'Pitch',symbol:'↕',slot:1,title:'Pitch / right stick',instruction:'Forward → back → centre. Keep roll centred.'},
 {name:'Yaw',symbol:'↔',slot:3,title:'Yaw / left stick',instruction:'Right → left → centre. Keep throttle still.'},
 {name:'Throttle',symbol:'↑',slot:2,title:'Throttle / left stick',instruction:'Down → up → down. Keep yaw centred.'},
 {name:'SA',symbol:'Ⅲ',slot:4,title:'SA / enable switch',instruction:'Low → middle → high. Finish at your chosen enable end.'}
];
const wizard={active:false,step:0,samples:{},first:{},baseline:{},mapping:null,candidate:null,ready:false};
function beginStep() {
 wizard.samples={};wizard.first={};wizard.baseline={...state.hid.axes};wizard.candidate=null;wizard.ready=false;
 Object.entries(state.hid.axes).forEach(([index,value])=>wizard.samples[index]=[value,value]);
 const step=steps[wizard.step];$('wizard-title').textContent=step.title;$('wizard-instruction').textContent=step.instruction;
 $('wizard-symbol').textContent=step.symbol;$('wizard-counter').textContent=`${wizard.step+1} / ${steps.length} · ${step.name.toUpperCase()}`;
 $('wizard-feedback').textContent='Move to both ends.';
 $('wizard-next').textContent=wizard.step===4?'Save mapping ✓':'Next →';$('wizard-next').disabled=true;
 $('wizard-min').textContent='—';$('wizard-max').textContent='—';$('wizard-axis').textContent='—';
 $('wizard-steps').replaceChildren(...steps.map((s,i)=>{let node=document.createElement('span');node.className='wizard-step'+(i===wizard.step?' active':i<wizard.step?' complete':'');node.title=s.name;return node;}));
}
function observeCalibration(hid) {
 if(!hid.connected){$('wizard-feedback').textContent='TX15 disconnected. Reconnect it to continue.';$('wizard-next').disabled=true;return;}
 const used=new Set(wizard.mapping.axes.filter(Boolean).map(a=>a.index));
 for(const [key,value] of Object.entries(hid.axes)) {
  if(used.has(Number(key)))continue;
  if(!wizard.samples[key]){wizard.samples[key]=[value,value];wizard.baseline[key]=value;}
  wizard.samples[key][0]=Math.min(wizard.samples[key][0],value);wizard.samples[key][1]=Math.max(wizard.samples[key][1],value);
  const delta=value-wizard.baseline[key];if(!wizard.first[key]&&Math.abs(delta)>10000)wizard.first[key]=Math.sign(delta);
 }
 const candidates=Object.entries(wizard.samples).filter(([key])=>!used.has(Number(key))).sort((a,b)=>(b[1][1]-b[1][0])-(a[1][1]-a[1][0]));
 if(!candidates.length)return;
 const [key,[min,max]]=candidates[0],span=max-min;
 $('wizard-min').textContent=min;$('wizard-max').textContent=max;$('wizard-axis').textContent=span>5000?'Input '+key:'—';
 wizard.ready=span>=50000;
 if(candidates[1]&&candidates[1][1][1]-candidates[1][1][0]>span*.65&&span>10000){wizard.ready=false;$('wizard-feedback').textContent='Multiple inputs moved. Retry.';showRetry();}
 else if(wizard.ready){
  wizard.candidate={index:Number(key),min,max,invert:wizard.first[key]<0};
  if(wizard.step===4){const current=hid.axes[key],middle=(min+max)/2;if(Math.abs(current-middle)<span*.3){wizard.ready=false;$('wizard-feedback').textContent='Choose the SA enable end.';}
   else{wizard.candidate={index:Number(key),min:current>middle?Math.round(middle+span*.25):min,max:current>middle?max:Math.round(middle-span*.25)};$('wizard-feedback').textContent=`SA ${current>middle?'high / position 3':'low / position 1'} selected. Save when you’re ready.`;}}
  else $('wizard-feedback').textContent='Range captured. Next when ready.';
 }else $('wizard-feedback').textContent=span>5000?'Reach both ends.':'Move only the requested control.';
 $('wizard-next').disabled=!wizard.ready;
}
function showRetry(){if($('wizard-retry'))return;let button=document.createElement('button');button.id='wizard-retry';button.className='secondary';button.textContent='Retry';button.addEventListener('click',()=>{button.remove();beginStep();});document.querySelector('.wizard-actions').append(button);}
$('wizard-start').addEventListener('click',()=>{
 if(!state?.hid.connected){notice('Connect the TX15 in USB joystick mode first.',true);return;}
 if(state.session.active){notice('Stop the bench session before calibration.',true);return;}
 wizard.active=true;wizard.step=0;wizard.mapping={note:'TX15 calibration from the Ascent setup console',axes:[null,null,null,null]};
 $('wizard-start').hidden=true;$('wizard-next').hidden=false;$('wizard-cancel').hidden=false;beginStep();
});
$('wizard-cancel').addEventListener('click',()=>{wizard.active=false;$('wizard-start').hidden=false;$('wizard-next').hidden=true;$('wizard-cancel').hidden=true;$('wizard-retry')?.remove();$('wizard-title').textContent='Calibration cancelled';$('wizard-instruction').textContent='Your previous calibration is unchanged.';$('wizard-feedback').textContent='No changes saved.';$('wizard-counter').textContent='SELF PACED';});
$('wizard-next').addEventListener('click',perform(async()=>{
 if(!wizard.ready)return;
 if(wizard.step<4){wizard.mapping.axes[steps[wizard.step].slot]=wizard.candidate;wizard.step++;$('wizard-retry')?.remove();beginStep();}
 else{wizard.mapping.deadman_axis=wizard.candidate;await api('mapping',wizard.mapping);wizard.active=false;$('wizard-start').hidden=false;$('wizard-start').textContent='Calibrate again';$('wizard-next').hidden=true;$('wizard-cancel').hidden=true;$('wizard-retry')?.remove();$('wizard-symbol').textContent='✓';$('wizard-title').textContent='TX15 mapped';$('wizard-instruction').textContent='Sticks and SA saved. Check them in TX15 view.';$('wizard-feedback').textContent='Saved locally · no output';$('wizard-counter').textContent='SAVED';notice('TX15 calibration saved.');}
}));

window.addEventListener('keydown',event=>{if(event.key==='Escape'){if(state?.session.active)stop();document.body.classList.remove('expanded');$('expand-video').setAttribute('aria-pressed','false');}});
page(location.hash.slice(1)||'live');
poll();
