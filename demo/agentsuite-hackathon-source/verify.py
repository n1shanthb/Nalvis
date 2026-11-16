"""Verify the exported MP4 and create timestamped scene review frames."""
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent
demo = root.parents[2]
ffmpeg = demo / 'video-tools/node_modules/ffmpeg-static/ffmpeg.exe'
ffprobe = demo / 'video-tools/node_modules/ffprobe-static/bin/win32/x64/ffprobe.exe'
video = root / 'out' / (root.name + '.mp4')
meta = json.loads(subprocess.check_output([str(ffprobe), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)]))
v = next(s for s in meta['streams'] if s['codec_type'] == 'video')
a = next(s for s in meta['streams'] if s['codec_type'] == 'audio')
assert (v['width'], v['height']) == (1920, 1080), v
assert abs(float(meta['format']['duration']) - 120) < 0.1, meta['format']['duration']
assert v['codec_name'] == 'h264' and a['codec_name'] == 'aac'
assert v['r_frame_rate'] == '30/1'
subprocess.run([str(ffmpeg), '-v', 'error', '-i', str(video), '-f', 'null', '-'], check=True)
frames = root / 'out' / 'review-frames'
frames.mkdir(exist_ok=True)
timeline = json.loads((root / 'timeline.json').read_text())
sheet = Image.new('RGB', (1600, 5 * 490), '#e8eef9')
draw = ImageDraw.Draw(sheet)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 24)
for i, scene in enumerate(timeline):
    target = frames / f'{i+1:02d}-{scene["id"]}.png'
    subprocess.run([str(ffmpeg), '-y', '-loglevel', 'error', '-ss', str(scene['midpoint']), '-i', str(video), '-frames:v', '1', str(target)], check=True)
    with Image.open(target) as image:
        image.thumbnail((780, 439))
        x, y = (i % 2) * 800 + 10, (i // 2) * 490 + 40
        sheet.paste(image, (x, y))
    sec = int(scene['midpoint'])
    draw.text((x, y - 32), f'{sec//60}:{sec%60:02d}  {scene["id"]}', fill='#173a7d', font=font)
sheet.save(root / 'out' / 'scene-review.jpg', quality=92)
report = {'duration':float(meta['format']['duration']), 'resolution':[v['width'],v['height']], 'fps':v['r_frame_rate'], 'videoCodec':v['codec_name'], 'audioCodec':a['codec_name'], 'bytes':video.stat().st_size, 'decodeCheck':'passed', 'reviewFrames':len(timeline), 'timeline':timeline}
(root / 'out' / 'verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:val for k,val in report.items() if k!='timeline'},indent=2))
