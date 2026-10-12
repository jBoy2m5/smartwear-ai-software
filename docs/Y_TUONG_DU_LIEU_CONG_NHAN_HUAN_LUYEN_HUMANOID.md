# SmartWear: từ kinh nghiệm công nhân đến hướng dẫn học việc và dữ liệu cho humanoid

**Tài liệu trình bày ý tưởng với ban giám khảo — 07/10/2026**
**Trạng thái:** đã có nguyên mẫu thu và xuất dữ liệu quan sát; chưa triển khai thu dữ liệu hàng trăm công nhân, chưa chứng minh người mới học nhanh hơn và chưa huấn luyện humanoid thực hiện công đoạn.

## Ý tưởng trong một phút

Trong cùng một công đoạn, người lao động có thể đạt kết quả bằng nhiều cách phối hợp tay khác nhau. SmartWear ghi lại **hình ảnh thao tác, thời gian, tín hiệu cảm biến và kết quả được người đánh giá xác nhận**. Từ nhiều lượt làm việc, hệ thống tạo hai đầu ra:

1. **Cho người mới:** một SOP có video theo bước, lý do của người hướng dẫn, dấu hiệu phải kiểm và ví dụ thao tác cần sửa.
2. **Cho nghiên cứu robot:** dữ liệu quan sát theo thời gian để tìm trình tự tiếp xúc, chuyển động và điều kiện dẫn đến sản phẩm đạt; về sau kết hợp với dữ liệu điều khiển của humanoid để huấn luyện và kiểm chứng robot.

Giả thuyết cần thử nghiệm là: khi so sánh **cùng công đoạn và điều kiện**, những lượt thành công ổn định sẽ bộc lộ các *vùng vận hành tốt* về thứ tự bước, thời điểm tiếp xúc, biến thiên lực và tốc độ, thay vì một “động tác chuẩn” duy nhất cho mọi người và mọi robot.

## Vì sao hướng này có cơ sở

- Nghiên cứu [MimicTouch](https://arxiv.org/abs/2310.16917) đã dùng trình diễn và dữ liệu xúc giác từ tay người để học thao tác có tiếp xúc, đồng thời bổ sung bước thích nghi từ tay người sang kẹp robot. Đây là bằng chứng về **hướng nghiên cứu**, không phải bằng chứng SmartWear đã đạt kết quả đó.
- [Human2Sim2Robot](https://arxiv.org/abs/2504.12609) cho thấy một cách lấy quỹ đạo vật và tư thế tay từ video người để xây dựng mục tiêu trong mô phỏng rồi chuyển sang robot. Công trình cũng nêu rõ video người thiếu nhãn hành động robot và có khác biệt cấu trúc tay.
- Mô hình điều khiển như [RT-2](https://robotics-transformer2.github.io/) được học từ cặp **quan sát và hành động robot**. Vì vậy dữ liệu công nhân giúp xác định nhiệm vụ, trạng thái và mục tiêu; để robot hành động cần thêm dữ liệu lệnh/trạng thái của chính robot hoặc một phép chuyển đổi đã được kiểm chứng.

## Cách kiểm chứng ý tưởng trong xưởng

**Đơn vị phân tích là một lượt làm một công đoạn**, có `task_id`, phiên bản quy trình, điều kiện vật/gá, người tham gia được mã hóa, thời gian bắt đầu/kết thúc, từng bước, sản phẩm đầu ra và người xác nhận. Ghi cả lượt đạt, không đạt và phải làm lại; nếu chỉ giữ lượt thành công, ta không biết yếu tố nào phân biệt thành công với thất bại.

| Cần ghi | Tác dụng |
|---|---|
| Video thấy tay, vật và điểm tiếp xúc; mốc bước được người xem duyệt | Hiểu *đã làm gì, khi nào và với vật nào* |
| Cảm biến từng ngón đã hiệu chuẩn, đơn vị và sai số | So sánh lực ở đúng bước; tránh gọi số ADC thô là Newton |
| Chuyển động 3D đã hiệu chuẩn và timestamp đồng bộ | Ước lượng tốc độ/vị trí vật lý; tránh gọi tốc độ pixel là mm/s |
| Kết quả vật lý: đạt/chưa đạt, lỗi, làm lại, thời gian chu kỳ | Xác định tiêu chí thành công từ sản phẩm, không từ nhãn AI |
| Điều kiện: loại linh kiện, gá, ca, tay thuận, thay đổi quy trình | So sánh các lượt tương đồng và phát hiện kết quả chỉ đúng trong một bối cảnh |

Phân tích từng bước, chẳng hạn lúc bắt ren hoặc đặt long đen: tìm **khoảng** lực/tốc độ và dạng đường thời gian thường gắn với sản phẩm đạt, có kèm số lượt và độ bất định. Cần cân bằng chất lượng, thời gian và an toàn; người nhanh nhất hoặc lực cao nhất không mặc nhiên là mẫu tốt nhất. Khác biệt về kinh nghiệm, linh kiện và gá có thể tạo ra tương quan giả. Vì vậy, sau phân tích hồi cứu phải kiểm lại trên **người, ca và lô linh kiện chưa dùng để xây mô hình**, rồi thử thay đổi hướng dẫn có kiểm soát. Chỉ khi kết quả thực cải thiện mới gọi đó là khuyến nghị thao tác.

Thu hàng trăm người **không phải điều kiện để bắt đầu**. Bắt đầu bằng một công đoạn, một số người hướng dẫn và người mới, xác nhận luồng thu–gán nhãn–đánh giá. Mở rộng dần sau khi có quy trình đồng ý ghi hình, quyền dùng dữ liệu, ẩn danh, kiểm chất lượng cảm biến và cách đánh giá sản phẩm thống nhất. Tách tập đánh giá theo **người/lượt**, không chia các khung hình liền kề của cùng video sang cả tập học và tập kiểm.

## Đường đi từ dữ liệu người đến humanoid

```text
Lượt công nhân + kết quả đã xác nhận
  → mốc bước, tiếp xúc, chuyển động và điều kiện thành công
  → mục tiêu thao tác theo vật và vùng vận hành đề xuất
  → mô phỏng hoặc điều khiển từ xa để tạo lệnh/trạng thái robot
  → học chính sách điều khiển có phản hồi cảm biến
  → thử trên humanoid với vật mới, ghi tỷ lệ đạt, lỗi và an toàn
```

Tay người và tay humanoid khác kích thước, số khớp, cảm biến, giới hạn lực và cách cầm vật. Vì thế **không chép trực tiếp giá trị lực ngón tay người thành lệnh lực robot**. Dữ liệu người trước hết giúp xác định *vật phải đi đâu, tiếp xúc ở đâu, thứ tự nào và điều kiện nào là đạt*. Nhóm robot chọn cấu trúc hành động, ghi trạng thái/lệnh robot, chuyển mục tiêu sang cơ cấu thật và thử nghiệm có giám sát. Một robot đạt trên vài video phát lại chưa chứng minh làm được công đoạn; phải đo sản phẩm đầu ra trên những lượt robot tự thực hiện.

## SmartWear đã làm được đến đâu

| Mức bằng chứng | Trạng thái ngày 07/10/2026 |
|---|---|
| Thu phần cứng thật | Sau phục hồi hotspot, lượt raw 10 giây có **179 JPEG và 501 mẫu SmartWrist**, khoảng **17,9 FPS và 50,0 Hz**; xem [báo cáo phục hồi](layer1-layer3/CAMERA-INCIDENT-20261007-EVENING.md). Đây là kiểm tra luồng thiết bị, chưa là phiên công đoạn được duyệt. |
| Xử lý và xuất dữ liệu | Một phiên đo cũ có **1.555 khung hình** được xuất HDF5/MCAP, tải lại và kiểm **12 artifact/13 checksum**; xem [báo cáo read-back](layer1-layer3/data-products-validation-resumed.json). Phiên đó chưa có SOP chuyên gia A/B được duyệt. |
| Giao diện cho người học | Đã có chọn công đoạn/reference, form ghi chú–duyệt, SOP HTML/video/clip và báo cáo chất lượng. Chưa có thí nghiệm người mới trước/sau học để kết luận hiệu quả đào tạo. |
| Lực và chuyển động vật lý | Bốn kênh hiện là **ADC thô ở tay phải**, kênh thứ tư không phản hồi trong lượt thử; IMU cổ tay thiếu dữ liệu. Camera QVGA chưa cho quỹ đạo 3D hoặc tốc độ mm/s đã kiểm chứng. Chưa công bố mức lực Newton tối ưu. |
| Humanoid | Chưa có robot, lệnh/trạng thái robot, phép chuyển đổi tay người–robot hoặc phép thử thành công trên robot. Dataset hiện là **observation-only**, `robot_policy_training_ready=false`. |

Ảnh thử gần nhất còn hướng vào khuôn mặt thay vì bàn thao tác. Trước khi trình diễn một công đoạn, phải chỉnh camera thấy rõ hai tay và linh kiện, quay mẫu thật, đánh dấu bước và để người hướng dẫn xác nhận kết quả. Hai bài mẫu khả thi cho demo hiện tại là **LOG: soạn/kiểm bộ** và **sản xuất: lắp bulông–long đen–đai ốc bằng tay**; xem [kế hoạch hai bài](DEMO_TWO_WORKFLOWS.md).

## Mốc nghiệm thu đề xuất

| Giai đoạn | Bằng chứng cần đưa cho người chấm |
|---|---|
| 1. Học việc | Mẫu hướng dẫn đã duyệt, người mới làm trước/sau khi xem SOP, sản phẩm được người đánh giá kiểm, thời gian và số lần gợi ý có nguồn thật. |
| 2. Phân tích nhiều người | Dữ liệu đủ lượt đạt và không đạt, cảm biến được hiệu chuẩn, báo cáo vùng thao tác tốt kèm độ bất định; kết quả kiểm trên người/ca/lô linh kiện độc lập. |
| 3. Chuyển sang humanoid | Bộ dữ liệu có quan sát **và** hành động robot, phép chuyển đổi/hiệu chuẩn, chạy thử trên robot thật; báo tỷ lệ thành công, lỗi, an toàn và điều kiện thử. |

**Câu trình bày ngắn:** “Chúng tôi đang xây nền tảng lưu kinh nghiệm thao tác thành hai tài sản có thể kiểm chứng: bài học cho người mới và dữ liệu quan sát cho robot. Nguyên mẫu đã thu, đồng bộ và xuất dữ liệu thật. Bước kế tiếp là chứng minh người mới học được một công đoạn; về dài hạn, thu nhiều lượt có kết quả để tìm vùng thao tác tốt và chuyển chúng thành mục tiêu huấn luyện humanoid. Chúng tôi chỉ gọi robot làm được việc sau khi có hành động robot và phép thử độc lập trên sản phẩm thật.”
