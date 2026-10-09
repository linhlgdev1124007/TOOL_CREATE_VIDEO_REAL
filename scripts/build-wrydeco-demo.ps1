$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'source\Wrydeco_real'
$work = Join-Path $root 'work\wrydeco-demo'
$output = Join-Path $root 'output'
New-Item -ItemType Directory -Force -Path $work, $output | Out-Null

$assembly = (Get-ChildItem (Join-Path $source 'video\2aOboR3pRachu*.mp4') | Select-Object -First 1).FullName
$workshop = (Get-ChildItem (Join-Path $source 'video\2aOboR1U*.mp4') | Select-Object -First 1).FullName
$leaves = (Get-ChildItem (Join-Path $source 'video\2aOboR2vH4*.mp4') | Select-Object -First 1).FullName
$hero = Join-Path $source 'Image\2aOboR3Xs9xDSaU0uJ2aaBgXq1PzkgHHMq9hA9J2.jpg'
$outro = Join-Path $source 'video_outro\outro_wrydeo.mp4'

$contentVideo = Join-Path $work 'wrydeco-content.mp4'
$narration = Join-Path $work 'wrydeco-narration.wav'
$masterAudio = Join-Path $work 'wrydeco-master-audio.m4a'

# A concise, product-specific US-English voiceover.
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice('Microsoft David Desktop')
$voice.Rate = 1
$voice.Volume = 100
$voice.SetOutputToWaveFile($narration)
$voice.Speak('This is not mass produced furniture. At Wrydeco, every branch is shaped, fitted, and finished by hand. The result is functional wood art, made to turn an ordinary room into an unforgettable space. Discover Wrydeco.')
$voice.Dispose()

# Build a compact vertical story with gentle cross-dissolves and restrained typography.
$font = 'C\:/Windows/Fonts/arialbd.ttf'
$videoFilter = @"
[0:v]scale=760:1352,crop=720:1280,zoompan=z='min(zoom+0.0007,1.06)':d=66:s=720x1280:fps=30,trim=duration=2.2,setpts=PTS-STARTPTS,fps=30,settb=AVTB[v0];
[1:v]trim=start=2.0:duration=4.2,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,eq=contrast=1.04:saturation=1.08,fps=30,settb=AVTB[v1];
[2:v]trim=start=3.0:duration=3.8,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,eq=contrast=1.04:saturation=1.06,fps=30,settb=AVTB[v2];
[3:v]trim=start=3.0:duration=4.5,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,eq=contrast=1.04:saturation=1.08,fps=30,settb=AVTB[v3];
[4:v]scale=760:1352,crop=720:1280,zoompan=z='min(zoom+0.00055,1.055)':d=114:s=720x1280:fps=30,trim=duration=3.8,setpts=PTS-STARTPTS,fps=30,settb=AVTB[v4];
[v0][v1]xfade=transition=fade:duration=0.4:offset=1.8[x1];
[x1][v2]xfade=transition=smoothleft:duration=0.4:offset=5.6[x2];
[x2][v3]xfade=transition=fade:duration=0.4:offset=9.0[x3];
[x3][v4]xfade=transition=fade:duration=0.45:offset=13.05,
drawbox=x=42:y=82:w=636:h=122:color=black@0.42:t=fill:enable='between(t,0,2.1)',
drawtext=fontfile='$font':text='HANDCRAFTED FROM NATURE':fontcolor=white:fontsize=38:x=(w-text_w)/2:y=118:enable='between(t,0,2.1)',
drawbox=x=70:y=1000:w=580:h=150:color=black@0.44:t=fill:enable='between(t,13.1,16.4)',
drawtext=fontfile='$font':text='FUNCTIONAL WOOD ART':fontcolor=white:fontsize=39:x=(w-text_w)/2:y=1034:enable='between(t,13.1,16.4)',
drawtext=fontfile='$font':text='Made one piece at a time':fontcolor=white:fontsize=27:x=(w-text_w)/2:y=1090:enable='between(t,13.1,16.4)',
setsar=1,format=yuv420p[vout]
"@ -replace "`r?`n", ''

& ffmpeg -hide_banner -loglevel error -y `
  -loop 1 -framerate 30 -i $hero `
  -i $assembly -i $workshop -i $leaves `
  -loop 1 -framerate 30 -i $hero `
  -filter_complex $videoFilter -map '[vout]' -an -t 16.4 `
  -c:v libx264 -preset medium -crf 19 -movflags +faststart $contentVideo
if ($LASTEXITCODE -ne 0) { throw 'Content video render failed.' }

# Preserve recognizable workshop sound under narration, then hand off to the supplied branded outro audio.
$audioFilter = @"
[0:a]atrim=start=2.0:duration=4.2,asetpts=PTS-STARTPTS,volume=0.18,adelay=1800|1800[a0];
[1:a]atrim=start=3.0:duration=3.8,asetpts=PTS-STARTPTS,volume=0.15,adelay=5600|5600[a1];
[2:a]atrim=start=3.0:duration=4.5,asetpts=PTS-STARTPTS,volume=0.16,adelay=9000|9000[a2];
[3:a]volume=1.35,highpass=f=90,lowpass=f=12000,adelay=250|250[vo];
[4:a]volume=1.0,adelay=16400|16400[brand];
[a0][a1][a2][vo][brand]amix=inputs=5:duration=longest:normalize=0,alimiter=limit=0.93,loudnorm=I=-15:LRA=7:TP=-1.5[aout]
"@ -replace "`r?`n", ''

& ffmpeg -hide_banner -loglevel error -y `
  -i $assembly -i $workshop -i $leaves -i $narration -i $outro `
  -filter_complex $audioFilter -map '[aout]' -t 19.08 -c:a aac -b:a 192k $masterAudio
if ($LASTEXITCODE -ne 0) { throw 'Master audio render failed.' }

Write-Output "CONTENT_VIDEO=$contentVideo"
Write-Output "MASTER_AUDIO=$masterAudio"
Write-Output "OUTRO=$outro"
