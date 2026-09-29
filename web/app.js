'use strict';
const $ = id => document.getElementById(id);
let state = null, hydrated = false, currentPage = 'controller', videoOpen = false, videoURL = '', noticeTimer;
const pageCopy = {
 controller: ['Make it feel familiar.', 'Your TX15, connected. Every movement, visible.'],
 calibration: ['A little setup. Total clarity.', 'One control at a time. No countdown to miss.'],
 connections: ['Bring the link together.', 'Radio, relay, video and flight controller in one place.'],
 bench: ['Your session. Your timing.', 'Start when you’re ready. Watch the flight controller respond.']
};
function notice(text, error = false) {
 clearTimeout(noticeTimer); $('notice').textContent = text; $('notice').hidden = false;
 $('notice').classList.toggle('error', error);
 noticeTimer = setTimeout(() => {$('notice').hidden = true;}, error ? 12000 : 6000);
}
async function api(action, data = {}) {
 if (!state) throw Error('Console is still connecting');
 const response = await fetch('/api/' + action, {method:'POST', headers:{'Content-Type':'application/json','X-Console-Token':state.token},body:JSON.stringify(data)});
 const result = await response.json(); if (!response.ok) throw Error(result.error || 'Operation failed'); return result;
}
function perform(fn) {return async () => {try {await fn();} catch(error) {notice(error.message, true);}};}
function page(name) {
 currentPage = name; document.querySelectorAll('.page').forEach(p => p.classList.toggle('active',p.id === 'page-' + name));
 document.querySelectorAll('.nav').forEach(p => p.classList.toggle('active',p.dataset.page === name));
 $('page-title').textContent = pageCopy[name][0]; $('page-description').textContent = pageCopy[name][1];
 if (name !== 'bench' && videoOpen) toggleVideo(false);
 window.scrollTo({top:0,behavior:'smooth'});
}
document.querySelectorAll('[data-page]').forEach(b => b.addEventListener('click',() => page(b.dataset.page)));
document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click',() => page(b.dataset.go)));
const channelNames = ['Roll','Pitch','Throttle','Yaw'];
function makeBar(name, id) {
 const row = document.createElement('div'); row.className = 'channel-row';
 row.innerHTML = `<div class="labels"><span>${name}</span><b id="${id}-value">—</b></div><div class="bar-track"><div class="bar-fill" id="${id}-fill"></div><i class="bar-marker" id="${id}-marker"></i></div>`;
 return row;
}
channelNames.forEach((name,i) => $('input-bars').append(makeBar(name,'input-' + i)));
[...channelNames, 'AUX1 / ARM'].forEach((name,i) => $('fc-bars').append(makeBar(name,'fc-' + i)));
function bar(id, value, min, max, suffix='') {
 const fraction = Number.isFinite(value) ? Math.max(0,Math.min(1,(value-min)/(max-min))) : 0;
 $(id+'-value').textContent = Number.isFinite(value) ? Math.round(value) + suffix : '—';
 $(id+'-fill').style.width = 100*fraction + '%'; $(id+'-marker').style.left = 100*fraction + '%';
}
function moveStick(prefix, x, y) {
 for (const name of [prefix+'-stick',prefix+'-stick-halo']) {
  $(name).setAttribute('cx', (prefix === 'left' ? 207 : 453) + 49*x);
  $(name).setAttribute('cy', 218 - 49*y);
 }
}
function fmtNumber(value, digits=1) {return Number.isFinite(value) ? value.toFixed(digits) : '—';}
function setPill(id, text, ok) {$(id).textContent = text; $(id).classList.toggle('ok',!!ok);}
function settingsFromForm() {
 return {host:$('host-input').value.trim(),transport:$('transport-input').value,
         seconds:Number($('duration-input').value),video_bitrate:Number($('bitrate-input').value)};
}
async function saveSettings(show=true) {
 await api('settings', settingsFromForm()); if(show) notice('Setup preferences saved.');
}
function render(s) {
 const hid = s.hid, fc = s.fc, pi = s.pi, session = s.session;
 if (!hydrated) {
  $('host-input').value=s.settings.host; $('transport-input').value=s.settings.transport;
  $('duration-input').value=s.settings.seconds; $('bitrate-input').value=s.settings.video_bitrate; hydrated=true;
 }
 setPill('radio-badge',hid.connected?'TX15 · connected':'TX15 · connect USB',hid.connected);
 setPill('link-badge',pi.connected?'Relay · '+pi.host:pi.checking?'Relay · checking':'Relay · unchecked',pi.connected);
 $('radio-stage').classList.toggle('disconnected',!hid.connected); $('hid-dot').classList.toggle('off',!hid.connected);
 $('hid-detail').textContent=hid.connected?'USB joystick connected · live preview':hid.error||'Connect TX15 USB joystick';
 $('radio-lcd').textContent=hid.connected?'USB CONNECTED':'CONNECT USB';
 const normalized = (hid.channels||[]).map(v => 2*(v-172)/1639-1);
 moveStick('left',normalized[3]||0,Number.isFinite(normalized[2])?normalized[2]:-1);
 moveStick('right',normalized[0]||0,normalized[1]||0);
 channelNames.forEach((n,i) => bar('input-'+i,hid.connected ? 1000 + (hid.channels[i]-172)*1000/1639 : null,1000,2000));
 const gate=s.mapping.deadman_axis;
 const sa=hid.connected && gate ? hid.axes[gate.index] : undefined;
 const saPosition=Number.isFinite(sa)?(sa < -12000?0:sa > 12000?2:1):-1;
 document.querySelectorAll('#sa-positions>div').forEach(p => p.classList.toggle('selected',Number(p.dataset.position)===saPosition));
 $('sa-title').textContent=saPosition>=0?['Position 1 · low','Position 2 · centre','Position 3 · high'][saPosition]:'Waiting for input';
 $('sa-number').textContent=saPosition<0?'—':['−100%','0%','+100%'][saPosition];
 $('sa-lever').setAttribute('d',['M160 85 L145 53','M160 85 L160 49','M160 85 L175 53'][Math.max(0,saPosition)]);
 $('sa-explainer').textContent=hid.enabled?'Selected enable position · ready for a bench test':'Bench enable is off. Move SA to its saved enable position.';
 $('fc-badge').textContent=fc.connected?'USB CONNECTED':'USB OFFLINE';
 $('fc-battery').textContent=fc.connected?fmtNumber(fc.voltage,2)+' V':'—';
 $('fc-receiver').textContent=fc.connected?(fc.sbus?'SBUS':'CHECK RX'):'—';
 $('fc-armed').textContent=fc.connected?(fc.armed?'ARMED':'DISARMED'):'—';
 $('fc-armed').style.color=fc.armed?'var(--red)':'var(--teal)';
 $('fc-detail').textContent=fc.connected?`TAKER H743 · ${fc.cells||0}S battery · read-only USB telemetry`:fc.error||'Connect the flight controller over USB';
 [0,1,3,2,4].forEach((source,i) => bar('fc-'+i,fc.connected?fc.channels[source]:null,987,2011));
 $('pi-state').textContent=pi.connected?'CONNECTED':pi.checking?'CHECKING':'UNCHECKED';
 $('ping-value').textContent=Number.isFinite(pi.ping_ms)?fmtNumber(pi.ping_ms)+' ms':'—';
 $('video-state').textContent=pi.connected?(pi.video==='active'&&pi.media==='active'?'Running':'Needs attention'):'—';
 $('receiver-state').textContent=pi.connected?(pi.receiver&&pi.driver&&pi.key?'Prepared':'Prepare relay'):'—';
 $('pi-detail').textContent=pi.error|| (pi.connected?'Connected to '+pi.hostname+'. Saved credentials stay on this laptop.':'Use Check connection to inspect the relay.');
 $('path-radio').classList.toggle('ok',hid.connected); $('path-pi').classList.toggle('ok',pi.connected); $('path-fc').classList.toggle('ok',fc.connected);
 $('toggle-fc').textContent=s.fc_enabled?'Release FC USB':'Connect FC USB';
 const requirements=[['TX15 connected',hid.connected],['SA in the selected enable position',hid.enabled],
  ['Throttle fully down',hid.connected&&hid.channels[2]<=210],['Relay connected and prepared',pi.connected&&pi.receiver&&pi.driver&&pi.key],
  ['FC connected, SBUS, disarmed',fc.connected&&fc.sbus&&!fc.armed]];
 $('readiness').replaceChildren(...requirements.map(([text,ok]) => {let row=document.createElement('div');row.className='ready-row'+(ok?' ok':'');let icon=document.createElement('i');icon.textContent=ok?'✓':'○';row.append(icon,document.createTextNode(text));return row;}));
 $('start-session').disabled=session.active||s.job.busy||wizard.active||requirements.some(r=>!r[1]);
 $('stop-session').disabled=!session.active;
 $('synthetic-test').disabled=session.active||s.job.busy||wizard.active||!requirements[3][1]||!requirements[4][1];
 $('session-title').textContent=session.active?(session.state==='live'?'Control is live.':'Starting session…'):session.state==='error'?'Session needs attention.':'Ready when you are.';
 $('session-description').textContent=session.active?session.message:session.state==='error'?session.message:'Start sends the four stick channels. All AUX stay low; returning SA to off ends the run.';
 $('frame-count').textContent=session.frames||0;
 $('session-clock').textContent=session.active?Math.max(0,Math.ceil(session.seconds-(Date.now()/1000-session.started)))+'s':'—';
 document.querySelector('.session-panel').classList.toggle('active-session',session.active);
 for (const id of ['check-pi','prepare-pi','save-connection','save-video','apply-bitrate','restart-video','toggle-fc','wizard-start','duration-input']) $(id).disabled=session.active||s.job.busy;
 $('check-pi').textContent=s.job.busy?s.job.message:'Check connection';
 const arm=s.arm_profile||{};
 $('arm-profile-state').textContent=arm.message||'Prepare the FC over USB';
 $('prepare-arm').disabled=session.active||s.job.busy||!fc.connected||fc.armed;
 $('restore-arm').disabled=session.active||s.job.busy||!fc.connected||fc.armed||!arm.ready;
 $('start-arm').disabled=session.active||s.job.busy||wizard.active||!arm.ready||!requirements[3][1]||!hid.connected||hid.enabled||hid.channels[2]>210;
 $('stop-arm').disabled=!session.active;
 $('arm-test-status').textContent=session.active&&session.kind==='arming'?session.message:session.kind==='arming'?session.message+` · ${session.frames||0} control frames`:'Begin with SA low and throttle down. Start opens a 30-second switch-test window.';
 $('arm-fc-status').textContent=fc.connected?`FC ${fc.armed?'ARMED':'DISARMED'} · blockers: ${(fc.arming_blockers||[]).join(', ')||'none'}`:'FC USB unplugged: motor/arming state is not available. Watch the drone or FPV OSD.';
 document.querySelector('.bench-badge span').textContent=session.active&&session.kind==='arming'?'ARM TEST':'ARM LOCKED';
 $('radio-lock').textContent=session.active&&session.kind==='arming'?'ARM TEST / IDLE ONLY':'ARM OUTPUT LOCKED';
 const names=['Roll','Pitch','Throttle','Yaw'];
 $('mapping-list').replaceChildren(...s.mapping.axes.map((axis,i)=>mappingRow(names[i],`Input ${axis.index} · ${axis.invert?'reversed':'normal'}`)),mappingRow('SA enable',gate?`Input ${gate.index} · ${gate.min>0?'high':gate.max<0?'low':'custom'}`:'Button'));
 const last=s.logs.at(-1); $('activity-latest').textContent=s.job.busy?s.job.message:last?last.text:'Live hardware preview';
 $('activity-log').replaceChildren(...s.logs.slice().reverse().map(log=>{let row=document.createElement('div');row.className='log-row '+log.level;let time=document.createElement('span');time.textContent=log.time;let text=document.createElement('span');text.textContent=log.text;row.append(time,text);return row;}));
 if(wizard.active) observeCalibration(hid);
}
function mappingRow(label,value) {let row=document.createElement('div');row.className='mapping-row';let a=document.createElement('span'),b=document.createElement('span');a.textContent=label;b.textContent=value;row.append(a,b);return row;}
let lastError=false;
async function poll() {
 try {const response=await fetch('/api/state',{cache:'no-store'});if(!response.ok)throw Error('Setup console unavailable');state=await response.json();render(state);if(lastError){notice('Console reconnected.');lastError=false;}}
 catch(error){if(!lastError)notice('Console connection lost. Control output will stop. Reconnecting…',true);lastError=true;}
 setTimeout(poll,120);
}
function toggleVideo(open=!videoOpen) {
 videoOpen=open; const container=$('video-container'); container.replaceChildren();
 if(open && state){videoURL=`http://${state.settings.host}:${state.settings.transport==='hls'?8888:8889}/fpv1/`;let frame=document.createElement('iframe');frame.title='FPV 01 live video';frame.src=videoURL;frame.allow='autoplay; fullscreen';container.append(frame);}
 else {let box=document.createElement('div');box.className='video-placeholder';box.innerHTML='<span>▷</span><h3>Your camera feed lives here.</h3><p>Open one player to keep network traffic low.</p>';container.append(box);}
 $('toggle-video').textContent=open?'Close live video':'Open live video';
}
$('toggle-video').addEventListener('click',()=>toggleVideo());
$('save-connection').addEventListener('click',perform(()=>saveSettings()));
$('save-video').addEventListener('click',perform(async()=>{await saveSettings();if(videoOpen)toggleVideo(false);}));
$('check-pi').addEventListener('click',perform(async()=>{await saveSettings(false);await api('check');}));
$('prepare-pi').addEventListener('click',perform(async()=>{await saveSettings(false);await api('prepare');}));
$('apply-bitrate').addEventListener('click',perform(async()=>{await saveSettings(false);await api('video_bitrate');notice('Applying bitrate. Video will reconnect.');}));
$('restart-video').addEventListener('click',perform(async()=>{await api('video_restart');notice('Restarting video and enabling Alfa WebRTC access.');}));
$('toggle-fc').addEventListener('click',perform(()=>api('fc',{enabled:!state.fc_enabled})));
$('start-session').addEventListener('click',perform(async()=>{await saveSettings(false);await api('start',{kind:'joystick'});}));
$('synthetic-test').addEventListener('click',perform(()=>api('start',{kind:'synthetic'})));
$('stop-session').addEventListener('click',perform(()=>api('stop')));
$('prepare-arm').addEventListener('click',perform(()=>api('arm_prepare')));
$('restore-arm').addEventListener('click',perform(()=>api('arm_restore')));
$('start-arm').addEventListener('click',perform(()=>api('start',{kind:'arming'})));
$('stop-arm').addEventListener('click',perform(()=>api('stop')));
$('duration-input').addEventListener('change',perform(()=>saveSettings(false)));

const steps=[
 {name:'Roll',symbol:'↔',slot:0,title:'Right stick. Right, then left.',instruction:'Move the right stick fully right, then fully left. Keep the other stick still. Return to centre when done.'},
 {name:'Pitch',symbol:'↕',slot:1,title:'Right stick. Forward, then back.',instruction:'Move the right stick fully forward, then fully back. Keep its left/right position centred. Return to centre.'},
 {name:'Yaw',symbol:'↔',slot:3,title:'Left stick. Right, then left.',instruction:'Move the left stick fully right, then fully left. Keep throttle still. Return left/right movement to centre.'},
 {name:'Throttle',symbol:'↑',slot:2,title:'Throttle. Down, up, then down.',instruction:'Start with throttle fully down. Move it fully up, then fully down again. Keep yaw centred.'},
 {name:'SA',symbol:'Ⅲ',slot:4,title:'SA. Visit all three positions.',instruction:'Move only SA through all three positions. Finish in the position you want to enable control—your chosen arming position.'}
];
const wizard={active:false,step:0,samples:{},first:{},baseline:{},mapping:null,candidate:null,ready:false};
function beginStep() {
 wizard.samples={};wizard.first={};wizard.baseline={...state.hid.axes};wizard.candidate=null;wizard.ready=false;
 Object.entries(state.hid.axes).forEach(([index,value])=>wizard.samples[index]=[value,value]);
 const step=steps[wizard.step];$('wizard-title').textContent=step.title;$('wizard-instruction').textContent=step.instruction;
 $('wizard-symbol').textContent=step.symbol;$('wizard-counter').textContent=`${wizard.step+1} / ${steps.length} · ${step.name.toUpperCase()}`;
 $('wizard-feedback').textContent='Move this control to both ends. Take your time.';
 $('wizard-next').textContent=wizard.step===4?'Save calibration ✓':'Next control →';$('wizard-next').disabled=true;
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
 if(candidates[1]&&candidates[1][1][1]-candidates[1][1][0]>span*.65&&span>10000){wizard.ready=false;$('wizard-feedback').textContent='More than one control moved. Click Retry this control and move only the requested control.';showRetry();}
 else if(wizard.ready){
  wizard.candidate={index:Number(key),min,max,invert:wizard.first[key]<0};
  if(wizard.step===4){const current=hid.axes[key],middle=(min+max)/2;if(Math.abs(current-middle)<span*.3){wizard.ready=false;$('wizard-feedback').textContent='Range captured. Leave SA at the end position you want to enable control.';}
   else{wizard.candidate={index:Number(key),min:current>middle?Math.round(middle+span*.25):min,max:current>middle?max:Math.round(middle-span*.25)};$('wizard-feedback').textContent=`SA ${current>middle?'high / position 3':'low / position 1'} selected. Save when you’re ready.`;}}
  else $('wizard-feedback').textContent='Full range captured. Click Next when you’re ready.';
 }else $('wizard-feedback').textContent=span>5000?'Movement detected. Reach both full ends to capture the range.':'Move only the requested control.';
 $('wizard-next').disabled=!wizard.ready;
}
function showRetry(){if($('wizard-retry'))return;let button=document.createElement('button');button.id='wizard-retry';button.className='secondary';button.textContent='Retry this control';button.addEventListener('click',()=>{button.remove();beginStep();});document.querySelector('.wizard-actions').append(button);}
$('wizard-start').addEventListener('click',()=>{
 if(!state?.hid.connected){notice('Connect the TX15 in USB joystick mode first.',true);return;}
 if(state.session.active){notice('Stop the bench session before calibration.',true);return;}
 wizard.active=true;wizard.step=0;wizard.mapping={note:'TX15 calibration from the Ascent setup console',axes:[null,null,null,null]};
 $('wizard-start').hidden=true;$('wizard-next').hidden=false;$('wizard-cancel').hidden=false;beginStep();
});
$('wizard-cancel').addEventListener('click',()=>{wizard.active=false;$('wizard-start').hidden=false;$('wizard-next').hidden=true;$('wizard-cancel').hidden=true;$('wizard-retry')?.remove();$('wizard-title').textContent='Calibration cancelled.';$('wizard-instruction').textContent='Your previous calibration is unchanged.';$('wizard-feedback').textContent='Live preview remains available.';$('wizard-counter').textContent='SELF PACED';});
$('wizard-next').addEventListener('click',perform(async()=>{
 if(!wizard.ready)return;
 if(wizard.step<4){wizard.mapping.axes[steps[wizard.step].slot]=wizard.candidate;wizard.step++;$('wizard-retry')?.remove();beginStep();}
 else{wizard.mapping.deadman_axis=wizard.candidate;await api('mapping',wizard.mapping);wizard.active=false;$('wizard-start').hidden=false;$('wizard-start').textContent='Recalibrate controls';$('wizard-next').hidden=true;$('wizard-cancel').hidden=true;$('wizard-retry')?.remove();$('wizard-symbol').textContent='✓';$('wizard-title').textContent='Your TX15 is set.';$('wizard-instruction').textContent='Your sticks and SA enable position are saved. Preview them on the Controller screen, then open Bench test when you’re ready.';$('wizard-feedback').textContent='Saved locally. ARM remains blocked for bench testing.';$('wizard-counter').textContent='SAVED';notice('TX15 calibration saved.');}
}));
window.addEventListener('keydown',event=>{if(event.key==='Escape'&&state?.session.active)api('stop').catch(()=>{});});
poll();
