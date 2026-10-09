"""Build local moving previews and evidence from the actual prepared/exported media."""
import argparse
import html
from pathlib import Path
import shutil
import pipeline as p


def preview(job):
    ready = p.read(job/"prepared.json")
    p.ff(["-i", ready["content"], "-i", ready["outro"], "-i", ready["audio"],
          "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
          "-t", ready["total_duration"], "-c:v", "libx264", "-preset", "fast", "-crf", "20",
          "-c:a", "copy", "-movflags", "+faststart", job/"draft-720.mp4"])
    plan = p.read(job/"edit-plan.json")
    frames, labels = [], []
    for i, clip in enumerate(plan["clips"]):
        for n, t in enumerate((.3, clip["duration"]/2, clip["duration"]-.1)):
            frame = job/f"scene-review-{i:02d}-{n}.jpg"
            p.ff(["-ss", t, "-i", job/f"scene-{i:02d}.mp4", "-frames:v", 1, "-vf", "scale=360:640", frame])
            frames.append(frame)
            labels.append(f"shot {i+1} / {t:.2f}s")
    p.sheet(frames, job/"scene-review.jpg", labels, columns=3)
    p.ff(["-i", job/"content.mp4", "-t", 2, "-an", "-c:v", "libx264", "-preset", "fast", job/"hook-a.mp4"])
    hero = job/f"scene-{len(plan['clips'])-1:02d}.mp4"
    p.ff(["-i", hero, "-i", job/"scene-00.mp4", "-filter_complex",
          "[0:v]trim=duration=1,setpts=PTS-STARTPTS[a];[1:v]trim=duration=1,setpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=1:a=0[v]",
          "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "fast", job/"hook-b.mp4"])


def comparison(job, baseline):
    # Lengths deliberately remain different; last frame holds only in this comparison artifact.
    p.ff(["-i", baseline, "-i", job/"reel.mp4", "-filter_complex",
          "[0:v]scale=360:640,setsar=1,tpad=stop_mode=clone:stop_duration=8[a];"
          "[1:v]scale=360:640,setsar=1[b];[a][b]hstack=shortest=1[v]",
          "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", 20,
          "-movflags", "+faststart", job/"before-after-silent.mp4"])


def page(job, baseline):
    import os
    old = Path(os.path.relpath(baseline, job)).as_posix()
    video = "reel.mp4" if (job/"reel.mp4").exists() else "draft-720.mp4"
    doc = f'''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Wrydeco · review bản dựng</title><style>
body{{background:#101614;color:#f5f0e6;font:16px/1.6 Arial;margin:0;padding:32px;max-width:1120px;margin:auto}}
h1{{font-weight:400}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:24px}}
video{{width:100%;max-height:70vh;background:#000}}a{{color:#dec59c}}article{{border-top:1px solid #576454;padding-top:12px}}
textarea{{width:100%;min-height:100px}} label{{display:block;margin:12px 0}}button{{padding:12px 24px}}
</style><h1>Wrydeco · Luxury có nhịp</h1>
<p>Xem ở tốc độ thật, bật âm thanh. Bản mới cần đánh giá cảm nhận về nhịp dựng, giọng đọc và phối âm trước khi hoàn tất.</p>
<div class="grid"><article><h2>Bản trước · v03</h2><video controls preload="metadata" src="{html.escape(old)}"></video></article>
<article><h2>Bản mới · v04</h2><video controls preload="metadata" src="{video}"></video></article></div>
<p><a href="storyboard.jpg">Storyboard cuối</a> · <a href="caption.txt">Caption và credit</a> · <a href="before-after-silent.mp4">So sánh hình: trái cũ, phải mới</a></p>
<h2>Hai phương án mở đầu</h2><div class="grid"><article><p>A · thao tác/cận khớp nối</p><video controls muted src="hook-a.mp4"></video></article>
<article><p>B · toàn bộ kệ rồi về thao tác</p><video controls muted src="hook-b.mp4"></video></article></div>
<h2>Ghi nhận review</h2><p>Kiểm tra: sản phẩm rõ; cut và chuyển động tự nhiên; màu gỗ hợp lý; chữ đọc được; voice rõ và tự nhiên; nhạc/SFX hợp hình; reveal và outro đủ.</p>
<label>Hình/chuyển động <select id="visual"><option value="unavailable">Chưa đánh giá</option><option value="pass">Đạt</option><option value="fail">Cần sửa</option></select></label>
<label>Nghe toàn bộ âm thanh <select id="listening"><option value="unavailable">Chưa nghe</option><option value="pass">Đạt</option><option value="fail">Cần sửa</option></select></label>
<label><input id="warnings" type="checkbox"> Đã đọc và xử lý các cảnh báo trong <a href="qa-report.json">QA report</a></label>
<label>Nhận xét cụ thể và timecode cần sửa<textarea id="notes" placeholder="Ví dụ 00:06: chữ che tay; 00:13: nhạc lấn voice..."></textarea></label>
<button id="save">Tải JSON review</button><p>Trang này không tự duyệt video hoặc đăng lên mạng xã hội.</p>
<script>document.getElementById('save').onclick=()=>{{const read=id=>document.getElementById(id);if(!read('notes').value.trim()){{alert('Hãy ghi nhận xét cụ thể.');return;}}const data={{visual:read('visual').value,listening:read('listening').value,warnings_resolved:read('warnings').checked,notes:read('notes').value,reviewer:'user',reviewed_at:new Date().toISOString()}};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}}));const a=document.createElement('a');a.href=url;a.download='user-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}};</script></html>'''
    (job/"review.html").write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preview", "comparison", "page"])
    parser.add_argument("--job", required=True)
    parser.add_argument("--baseline", required=True)
    args = parser.parse_args()
    job, baseline = Path(args.job).resolve(), Path(args.baseline).resolve()
    if not job.is_relative_to(p.ROOT/"output"):
        parser.error("Job must be under output")
    with p.job_lock():
        if args.command == "preview":
            preview(job)
        elif args.command == "comparison":
            comparison(job, baseline)
        page(job, baseline)
