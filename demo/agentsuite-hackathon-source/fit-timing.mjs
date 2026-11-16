// Keep the approved words, fit the narration to a precise two-minute timeline.
// Source TTS files remain untouched, preserving UltraDemo's narration cache.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(fileURLToPath(import.meta.url));
const assets=path.join(root,'assets');
const sb=JSON.parse(readFileSync(path.join(assets,'storyboard.json'),'utf8'));
const cameras={'s04-specialist':{x:1000,y:430,zoom:1.18},'s05-policy':{x:550,y:300,zoom:1.25},'s06-run':{x:1920,y:0,zoom:1.2},'s07-evidence':{x:600,y:360,zoom:1.55},'s09-limits':{x:1920,y:0,zoom:1.15}};
for(const s of sb.scenes)if(cameras[s.id])s.focus=cameras[s.id];
sb.scenes.find(s=>s.id==='s03-context').caption={position:'top'};
const units=[['intro-slide',sb.intro,12,true],...sb.scenes.map((s,i)=>[s.id,s,[8,12,12,10,16,16,16,8][i],false]),['outro-slide',sb.outro,10,true]];
const probe=f=>Number(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',f]).toString());
mkdirSync(path.join(assets,'audio','timed'),{recursive:true});
let start=0;const timeline=[];
for(const [id,obj,seconds,slide] of units){
 const source=path.join(assets,'audio',id+'.mp3');
 const duration=probe(source);
 const budget=seconds-(slide?1.45:0.7);
 const rate=Math.max(0.85,duration/budget);
 if(rate>1.45) throw new Error(`${id}: needs excessive speed ${rate.toFixed(2)}`);
 const output=path.join(assets,'audio','timed',id+'.wav');
 execFileSync('ffmpeg',['-y','-loglevel','error','-i',source,'-af',`atempo=${rate.toFixed(8)},apad,atrim=duration=${budget}`,'-ar','48000','-ac','1',output]);
 obj.audio=`audio/timed/${id}.wav`; obj.audioDuration=budget;
 delete obj.words;
 timeline.push({id,start,duration:seconds,midpoint:start+seconds/2,sourceAudioDuration:duration,speechRate:rate});
 start+=seconds;
}
if(start!==120)throw new Error('Timeline must equal 120 seconds');
writeFileSync(path.join(assets,'storyboard.json'),JSON.stringify(sb,null,2));
writeFileSync(path.join(root,'timeline.json'),JSON.stringify(timeline,null,2));
console.log(timeline);console.log('Timeline: 3600 frames / 120 seconds');
