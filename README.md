# TOOL_CREATE_VIDEO_REAL — Wrydeco Reels

Dựng Reel từ ảnh sản phẩm và footage xưởng thật: phân tích nguồn, voice US English
bằng Kokoro local, nhạc/SFX có provenance, dựng qua OpenCut MCP và kiểm định file
xuất. Google Flow là phần **tùy chọn**, dùng cho cảnh phụ không có sản phẩm/người.
Không tự đăng video lên mạng xã hội.

## Yêu cầu Agent cài tự động

Mở thư mục repository trong coding agent có quyền terminal và gửi:

> Đọc toàn bộ README.md. Hãy cài đặt project theo runbook bên dưới, gồm cả
> Flowkit. Tự làm các bước máy có thể làm, chạy kiểm tra và sửa lỗi cài đặt.
> Chỉ báo tôi khi cần đăng nhập, xác nhận của hệ điều hành, cài extension trong
> Chrome hoặc cung cấp media/URL Google Flow. Không tạo video trên Flow hay tiêu
> credit chỉ để thử cài đặt.

README là chỉ dẫn cho agent, không tự chạy khi mở file. Agent cần terminal,
Internet và quyền ghi vào thư mục project. Agent chỉ đọc văn bản không cài được.

## Yêu cầu máy

- **Windows 10/11 x64, PowerShell**: nền tảng đã kiểm thử.
- **Python 3.13 x64**, Git, Bun, FFmpeg + ffprobe. Script có thể cài công cụ thiếu
  qua `winget` (Microsoft App Installer).
- Dung lượng cho dependencies, Chromium, model voice và media. Model/cache có thể
  tải hàng trăm MB; footage và video đầu ra có thể lớn hơn nhiều.
- Internet cho lần cài đầu và Google Flow. Không cần API key để tạo voice local
  hoặc dựng OpenCut. Không có API nghe/đánh giá âm thanh được cấu hình sẵn.
- Chrome desktop và tài khoản Google có quyền dùng Flow nếu bật Flowkit.
  Chromium riêng của OpenCut không thay thế Chrome đã đăng nhập của bạn.

Không bắt buộc Docker, GPU, Rust toolchain, database, Redis hay tài khoản OpenCut
cho luồng dựng local hiện tại.

## Runbook cho Agent

### 1. Lấy mã

```powershell
git clone https://github.com/linhlgdev1124007/TOOL_CREATE_VIDEO_REAL.git
cd TOOL_CREATE_VIDEO_REAL
```

Nếu chưa có Git, có thể tải ZIP trên GitHub rồi giải nén. Các lệnh bên dưới chạy
tại thư mục có README. Script tính đường dẫn từ vị trí repository, không bắt buộc
ổ `D:`. Đổi đường dẫn tuyệt đối trong các ví dụ/legacy demo theo máy thực tế.
Không chạy demo cũ để thay cho pipeline mới.

### 2. Cài đặt tự động

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -InstallPrerequisites -WithFlowkit
```

`ExecutionPolicy Bypass` chỉ áp dụng cho tiến trình này, không sửa policy toàn máy.
Nếu máy tổ chức chặn installer/script, báo đúng lỗi, không lách chính sách.

Script sẽ:

1. Tìm/cài Git, FFmpeg, Bun và Python 3.13 còn thiếu qua winget.
2. Clone OpenCut/MCP đúng commit trong `dependencies.lock.json`; áp dụng patch và
   source bổ sung ở `patches/`. Không ghi đè local edits có xung đột.
3. Tạo `.venv-reels`, cài Python packages, Bun dependencies theo lockfile,
   Playwright Chromium headless, model Kokoro và nhạc/SFX starter library.
4. Với `-WithFlowkit`: clone Flowkit đúng pin, tạo `.venv-flowkit` và cài dependencies.
5. Chạy `scripts/doctor.py` kiểm tra cài đặt.

Bỏ `-WithFlowkit` nếu chỉ dựng media thật. Bỏ `-InstallPrerequisites` nếu đã có
công cụ hệ thống. Có thể chạy lại; không reset checkout hoặc xóa media người dùng.
Nếu vừa cài mà PATH chưa cập nhật, mở terminal mới và chạy lại. Nếu thiếu winget,
bạn cần cài Microsoft App Installer hoặc tự cài Git, Python 3.13, Bun, FFmpeg từ
nhà cung cấp chính thức.

Agent phải chạy các lệnh kiểm tra sau, dừng và xử lý nếu lỗi:

```powershell
.\.venv-reels\Scripts\python.exe scripts/doctor.py
.\.venv-reels\Scripts\python.exe -m unittest discover -s reels -p 'test_*.py'
Push-Location opencut-mcp
bun run build
bun test tests
Pop-Location
```

Để chạy cả fixture FFmpeg: đặt `$env:REELS_INTEGRATION='1'` trước unittest.
Chỉ chạy một render tại một thời điểm. Doctor kiểm tra cài đặt, không chứng nhận
chất lượng video hoặc kết nối tài khoản Flow.

### 3. Những việc bạn cần làm

| Công việc | Ai làm? |
| --- | --- |
| Cài dependencies, model, audio library, server và kiểm tra lỗi | Agent |
| Xác nhận UAC/installer nếu hệ điều hành yêu cầu | Bạn |
| Cung cấp ảnh/video thật và outro thương hiệu | Bạn |
| Đăng nhập Google, xác thực hai bước, xử lý challenge hợp lệ | Bạn |
| Bật Developer mode và Load unpacked trong Chrome | Bạn theo hướng dẫn dưới |
| Gửi URL project Flow và hạn mức tạo cảnh được phép | Bạn |
| Kiểm tra kết nối, tạo/import cảnh được phép, dựng và QA | Agent |

Không gửi mật khẩu, cookie hoặc token cho agent. Không đưa browser profile,
`.env` hay credentials vào Git.

### 4. Cài extension Flowkit trong Chrome

Làm sau khi setup `-WithFlowkit` thành công:

1. Mở **Chrome desktop**, chọn đúng profile Google bạn sẽ sử dụng.
2. Vào **`chrome://extensions`**.
3. Bật **Developer mode / Chế độ dành cho nhà phát triển** ở góc trên phải.
4. Bấm **Load unpacked / Tải tiện ích đã giải nén**.
5. Chọn **`<thư-mục-project>\integrations\flowkit\extension`**, là thư mục chứa
   `manifest.json`. Không chọn file ZIP hoặc thư mục `flowkit` cha.
6. Kiểm tra extension bật. Phiên bản tại pin hiện tại là **0.3.4**; không tự
   nâng cấp upstream trước khi kiểm tra tương thích.
7. Trong cùng Chrome profile, mở **https://flow.google.com**, đăng nhập, mở/tạo
   project và gửi agent URL dạng **`https://flow.google.com/project/<UUID>`**.
8. Giữ tab Flow đã đăng nhập mở khi agent làm việc. Nếu Google yêu cầu đăng nhập
   lại hoặc challenge, bạn xử lý trên giao diện Google bình thường.

Nếu chưa có Chrome, cài Chrome desktop trước. Nếu trình duyệt do tổ chức quản lý
chặn Developer mode/extension, liên hệ quản trị viên hoặc dùng pipeline không
có Flow. Không lách hạn chế của trình duyệt/tài khoản.

### 5. Agent khởi động và kiểm tra Flow

Thay `<UUID>` bằng phần cuối URL và `<job>` bằng tên job thực:

```powershell
powershell -File scripts/start-flowkit.ps1 -ProjectId '<UUID>' -Job 'output/<job>'
.\.venv-reels\Scripts\python.exe reels/flowkit_adapter.py health --project-id '<UUID>' --job 'output/<job>'
```

Kết quả cần **`ready: true`**, `extension_connected: true`, đúng `project_id`.
Server dùng localhost HTTP **8100**, WebSocket **9222**; không mở port ra Internet.
`flow_key_present: false` không tự nó là lỗi ở batch transport hiện tại.
Health check không tạo video hoặc tiêu credit.

Khi dừng server hoặc đổi project:

```powershell
powershell -File scripts/stop-flowkit.ps1 -Job 'output/<job>'
```

Sau đó start lại với UUID mới. Giữ budget của job; không đổi project để né chặn.
Script chỉ dừng process nó sở hữu, không tắt Chrome của bạn.

### 6. Chuẩn bị media và dựng video

Media cá nhân **không nằm trong Git**. Chép theo [source/README.md](source/README.md):

```text
source/Wrydeco_real/
  Image/
  video/
  video_outro/     # bắt buộc
  video_final/     # tùy chọn, chỉ tham khảo
```

Ví dụ yêu cầu Agent:

> Đọc README và skill wrydeco-reels. Tạo một Reel từ source/Wrydeco_real,
> luxury có nhịp, 1080×1920, khoảng 20 giây. Tự phân tích media và chọn một sản
> phẩm nhất quán. Dùng Flow project [URL] cho cảnh phụ nếu cần; cho phép tối đa
> 6 lượt tạo, không mua credit. Giữ sản phẩm và thao tác xưởng thật.

Agent đọc `.agents/skills/wrydeco-reels/SKILL.md`, phân tích ảnh/storyboard thực tế,
chọn một câu chuyện và viết `edit-plan.json`. Không chọn cảnh chỉ theo tên file.

```powershell
.\.venv-reels\Scripts\python.exe reels/pipeline.py analyze --source source/Wrydeco_real --job output/my-reel-v01
```

Tiếp theo: `validate → voice → prepare → export → qa → review`, mỗi lệnh nhận
`--job output/my-reel-v01`. `review` nhận thêm `--review-file <review.json>`.
Xem [schema plan/review](.agents/skills/wrydeco-reels/references/edit-plan.md)
và [hướng dẫn v2](reels/REELS_V2.md). Phải có outro thật trong plan.

**Plan v2** hỗ trợ 720p/1080p, speed ramp, motion keyframe, color, title và fade
có thời lượng cấu hình. Các giới hạn v1 trong skill cũ không phủ định tính năng
v2. Chưa có tracking, masking hay stabilization.

OpenCut chạy riêng tại port **3037** khi export, tạo timeline qua MCP với content,
outro và master audio. Sau khi xuất, script đóng tiến trình do nó khởi tạo.

Flow chỉ tạo atmosphere không có sản phẩm/người: tối đa 2 cảnh, tổng không quá
2 giây trong Reel. Sáu lượt là trần của một job, **không phải quyền mặc định tiêu
credit khi cài đặt**. Lượt lỗi/không rõ kết quả vẫn tính trong `flow/budget.json`;
không xóa budget hay gửi lại ID chưa rõ trạng thái. Submit/poll/import và review
cảnh AI được mô tả trong `reels/REELS_V2.md`.

### 7. QA và bàn giao

- Xem storyboard của file cuối; kiểm crop, chữ, đúng sản phẩm và outro. Xem
  playback nếu công cụ thực sự hỗ trợ; contact sheet không chứng nhận chuyển động.
- Kiểm codec, fps, pixel ratio, đồng bộ A/V, decode, LUFS/true peak, voice trước outro.
- Chỉ có voice + nhạc + SFX. Mute audio nguồn/outro; nhạc tiếp tục qua outro.
- Phân biệt đo tín hiệu và nghe: nếu agent không nhận được audio, ghi
  `listening: unavailable`, giữ **`needs_review`**, không tự tuyên bố phối âm hay.
- Không cam kết triệu view hoặc dùng điểm heuristic làm chứng nhận retention.
- Bàn giao `reel.mp4`, `storyboard.jpg`, `caption.txt`, `qa-report.json` trong job.
  **Giữ credit nhạc trong caption khi đăng.** Không tự đăng Facebook.

## Xử lý lỗi

| Lỗi | Cách xử lý |
| --- | --- |
| Thiếu command/PATH sau cài | Mở terminal mới, chạy bootstrap/doctor lại |
| Python packages không cài được | Dùng Python 3.13 x64; kiểm pip error trước khi đổi lock |
| Clone/patch lỗi | Kiểm commit và local edits; không reset hard hoặc ghi đè |
| Download lỗi | Sửa kết nối, chạy setup lại; không tắt TLS verification |
| Extension không kết nối | Server phải chạy; kiểm Chrome profile/tab/extension, Reload extension và refresh tab |
| Port 8100/9222/3037 bận | Xác định chủ process; không kill ứng dụng không liên quan |
| Google báo unusual activity/challenge | Dừng submit; bạn xử lý trên Flow UI, không bypass/auto-retry |
| Thiếu credit/quyền dùng Flow | Báo đúng lỗi, dùng media thật; không tự mua credit |
| Lock `work/reels.lock` còn | Kiểm PID, chỉ xóa nếu xác nhận process đã chết |
| Thiếu media/outro | Bạn cung cấp; clone Git không tải media cá nhân |

## Cấu trúc và bảo trì

```text
.agents/skills/          chỉ dẫn biên tập cho agent
reels/                  pipeline, audio, effects, Flow adapter, tests
scripts/                bootstrap, doctor, restore dependencies, quản lý Flow
patches/                MCP patch + source bổ sung + upstream license
dependencies.lock.json  URL và commit OpenCut/MCP đã kiểm thử
source/                 media người dùng, bị Git bỏ qua
output/                 video và báo cáo, bị Git bỏ qua
```

Setup khôi phục `opencut-classic/`, `opencut-mcp/`, `integrations/flowkit/`,
`.venv-*`, `.cache/`, `reels/assets/`; không commit nguyên thư mục dependency.
Nếu sửa MCP, chạy **`python scripts/snapshot-opencut-mcp.py`**, xem diff trong
`patches/` rồi commit. Sửa riêng checkout MCP sẽ không tự lên repository gốc.
Xem [THIRD_PARTY.md](THIRD_PARTY.md) về nguồn và giấy phép.
