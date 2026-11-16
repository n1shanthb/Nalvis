import {execFileSync} from 'node:child_process';
import {mkdirSync,renameSync} from 'node:fs';
const project='agentsuite-hackathon-2026-10-17-1200';
const out=`projects/${project}/out`;
for(const [name,frames] of [['governance','1320-2099'],['limits','3060-3299']]){
 execFileSync(process.execPath,['node_modules/@remotion/cli/remotion-cli.js','render','render/src/index.ts','Demo',`${out}/${name}-corrected.mp4`,`--public-dir=projects/${project}/assets`,`--frames=${frames}`,'--concurrency=8','--timeout=90000','--browser-executable=C:/Users/Nishanth/AppData/Local/ms-playwright/chromium-1228/chrome-win64/chrome.exe'],{stdio:'inherit'});
}
const original=`${out}/${project}.mp4`;
const corrected=`${out}/${project}-corrected.mp4`;
execFileSync('../video-tools/node_modules/ffmpeg-static/ffmpeg.exe',['-y','-loglevel','error','-i',original,'-i',`${out}/governance-corrected.mp4`,'-i',`${out}/limits-corrected.mp4`,'-filter_complex','[0:v]trim=start=0:end=44,setpts=PTS-STARTPTS[v0];[1:v]trim=duration=26,setpts=PTS-STARTPTS[v1];[0:v]trim=start=70:end=102,setpts=PTS-STARTPTS[v2];[2:v]trim=duration=8,setpts=PTS-STARTPTS[v3];[0:v]trim=start=110:end=120,setpts=PTS-STARTPTS[v4];[v0][v1][v2][v3][v4]concat=n=5:v=1:a=0[v]','-map','[v]','-map','0:a','-af','atrim=duration=120,asetpts=PTS-STARTPTS','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t','120','-movflags','+faststart',corrected],{stdio:'inherit'});
mkdirSync(`${out}/archive`,{recursive:true});
renameSync(original,`${out}/archive/first-framing.mp4`);
renameSync(corrected,original);
console.log('Corrected framing assembled, original preserved.');
