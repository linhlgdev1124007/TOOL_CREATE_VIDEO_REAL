# Media cá nhân — không đưa vào Git

Sau khi clone, chép media thật theo cấu trúc:

```text
source/Wrydeco_real/
  Image/          ảnh sản phẩm
  video/          footage thật tại xưởng
  video_outro/    outro thương hiệu (bắt buộc)
  video_final/    video tham khảo (tùy chọn)
```

Agent phải phân tích nội dung trước khi chọn clip. Không dùng video tham khảo làm
footage hoặc tái sử dụng nhạc chưa có giấy phép. Có thể cung cấp thư mục nguồn ở
nơi khác qua `pipeline.py analyze --source <folder>`. Không có media thực hoặc
outro thì báo đúng phần còn thiếu, không tự tạo sản phẩm thay thế.
