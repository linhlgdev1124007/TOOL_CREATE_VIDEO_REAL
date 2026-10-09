$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'source\Wrydeco_real'
$work = Join-Path $root 'work\hy-video'
$delivery = Join-Path $root 'hy'
New-Item -ItemType Directory -Force -Path $work, $delivery | Out-Null

$videos = Get-ChildItem (Join-Path $source 'video') -File | Sort-Object Name | Select-Object -First 5
$fit = $videos[4].FullName
$drill = $videos[3].FullName
$shape = $videos[2].FullName
$images = Get-ChildItem (Join-Path $source 'Image') -File | Sort-Object Name
$heroFront = $images[5].FullName
$heroSide = $images[13].FullName
$outro = Join-Path $source 'video_outro\outro_wrydeo.mp4'

$contentVideo = Join-Path $work 'bench-content.mp4'
$narration = Join-Path $work 'bench-narration.wav'
$masterAudio = Join-Path $work 'bench-master-audio.m4a'

Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice('Microsoft David Desktop')
$voice.Rate = 1
$voice.Volume = 100
$voice.SetOutputToWaveFile($narration)
$voice.Speak('A bench should do more than fill a space. Wrydeco pairs a live edge slab with sculptural natural wood, fitted and secured by hand. Every curve keeps the character of the tree, creating a functional statement piece, made one at a time. Discover Wrydeco.')
$voice.Dispose()

$font = 'C\:/Windows/Fonts/arialbd.ttf'
$videoFilter = @"
[0:v]scale=760:1352,crop=720:1280,zoompan=z='min(zoom+0.00065,1.055)':d=66:s=720x1280:fps=30,trim=duration=2.2,setpts=PTS-STARTPTS,fps=30,settb=AVTB[v0];
[1:v]trim=start=2.0:duration=4.2,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,eq=contrast=1.04:saturation=1.07,fps=30,settb=AVTB[v1];
[2:v]trim=start=10.0:duration=3.8,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,eq=contrast=1.04:saturation=1.06,fps=30,settb=AVTB[v2];
[3:v]trim=start=3.0:duration=4.5,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,eq=contrast=1.04:saturation=1.07,fps=30,settb=AVTB[v3];
[4:v]scale=760:1352,crop=720:1280,zoompan=z='min(zoom+0.00055,1.05)':d=114:s=720x1280:fps=30,trim=duration=3.8,setpts=PTS-STARTPTS,fps=30,settb=AVTB[v4];
[v0][v1]xfade=transition=fade:duration=0.4:offset=1.8[x1];
[x1][v2]xfade=transition=smoothleft:duration=0.4:offset=5.6[x2];
[x2][v3]xfade=transition=fade:duration=0.4:offset=9.0[x3];
[x3][v4]xfade=transition=fade:duration=0.45:offset=13.05,
drawbox=x=55:y=82:w=610:h=122:color=black@0.42:t=fill:enable='between(t,0,2.1)',
drawtext=fontfile='$font':text='NATURE, SHAPED BY HAND':fontcolor=white:fontsize=37:x=(w-text_w)/2:y=118:enable='between(t,0,2.1)',
drawbox=x=68:y=1000:w=584:h=150:color=black@0.44:t=fill:enable='between(t,13.1,16.4)',
drawtext=fontfile='$font':text='LIVE-EDGE CRAFTSMANSHIP':fontcolor=white:fontsize=34:x=(w-text_w)/2:y=1034:enable='between(t,13.1,16.4)',
drawtext=fontfile='$font':text='One piece at a time':fontcolor=white:fontsize=27:x=(w-text_w)/2:y=1090:enable='between(t,13.1,16.4)',
setsar=1,format=yuv420p[vout]
"@ -replace "`r?`n", ''

& ffmpeg -hide_banner -loglevel error -y `
  -loop 1 -framerate 30 -i $heroFront `
  -i $fit -i $drill -i $shape `
  -loop 1 -framerate 30 -i $heroSide `
  -filter_complex $videoFilter -map '[vout]' -an -t 16.4 `
  -c:v libx264 -preset medium -crf 19 -movflags +faststart $contentVideo
if ($LASTEXITCODE -ne 0) { throw 'Bench content render failed.' }

$audioFilter = @"
[0:a]atrim=start=2.0:duration=4.2,asetpts=PTS-STARTPTS,volume=0.18,adelay=1800|1800[a0];
[1:a]atrim=start=10.0:duration=3.8,asetpts=PTS-STARTPTS,volume=0.14,adelay=5600|5600[a1];
[2:a]atrim=start=3.0:duration=4.5,asetpts=PTS-STARTPTS,volume=0.16,adelay=9000|9000[a2];
[3:a]volume=1.35,highpass=f=90,lowpass=f=12000,adelay=250|250[vo];
[4:a]volume=1.0,adelay=16400|16400[brand];
[a0][a1][a2][vo][brand]amix=inputs=5:duration=longest:normalize=0,alimiter=limit=0.93,loudnorm=I=-15:LRA=7:TP=-1.5[aout]
"@ -replace "`r?`n", ''

& ffmpeg -hide_banner -loglevel error -y `
  -i $fit -i $drill -i $shape -i $narration -i $outro `
  -filter_complex $audioFilter -map '[aout]' -t 19.08 -c:a aac -b:a 192k $masterAudio
if ($LASTEXITCODE -ne 0) { throw 'Bench master audio render failed.' }

Write-Output "CONTENT_VIDEO=$contentVideo"
Write-Output "MASTER_AUDIO=$masterAudio"
Write-Output "NARRATION=$narration"
