import json,subprocess,sys
from pathlib import Path
from PIL import Image
sys.path.insert(0,'/home/dadrout/WizeTale/wizetale-api')
from app.services.video.ffmpeg_service import FFmpegService
out=Path('/home/dadrout/WizeTale/artifacts/verification-2026-10-20')
Image.new('RGB',(768,1024),(35,77,61)).save(out/'portrait-fixture.png')
Image.new('RGB',(1280,720),(247,245,238)).save(out/'landscape-fixture.png')
(out/'captions.srt').write_text('1\n00:00:00,000 --> 00:00:02,000\nVerification fixture.\n',encoding='utf8')
r=subprocess.run(['ffmpeg','-y','-f','lavfi','-i','sine=frequency=440:duration=2','-c:a','pcm_s16le',str(out/'fixture.wav')],capture_output=True,text=True)
assert r.returncode==0,r.stderr[-1000:]
service=FFmpegService()
for static in [False,True]:
 p=out/('presentation-smoke.mp4' if static else 'story-smoke.mp4')
 service.render(image_paths=[str(out/'portrait-fixture.png'),str(out/'landscape-fixture.png')],scene_durations=[1.0,1.0],audio_path=str(out/'fixture.wav'),audio_duration=2,subtitles_path=str(out/'captions.srt'),output_path=str(p),static_slides=static)
 probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,codec_name,width,height:format=duration','-of','json',str(p)],capture_output=True,text=True,check=True)
 data=json.loads(probe.stdout)
 assert any(s.get('codec_type')=='video' and s.get('width')==1280 and s.get('height')==720 for s in data['streams'])
 assert any(s.get('codec_type')=='audio' for s in data['streams'])
 assert 1.8<=float(data['format']['duration'])<=2.5
 print(p.name,json.dumps(data),flush=True)
