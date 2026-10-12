# Demo SmartWear: hai công đoạn, hai loại đầu ra

Ngày lập: 07/10/2026. Trạng thái: **kịch bản thực nghiệm và SOP mẫu đã soạn; chưa có phiên quay xác nhận theo hai công đoạn này**.

Cập nhật phần mềm: dashboard đã có lựa chọn role/task/reference, form notes/review và export dữ liệu quan sát. Xem [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md) và [phiếu thực nghiệm](demo-kit/EVIDENCE.md) để thao tác theo từng bước. Các checklist nghiệm thu dưới đây vẫn chưa đạt khi chưa quay/đánh giá thật.

Thông tin người dùng xác nhận: còn **3 ngày tới deadline**, đã có hộp/khay, SmartCap và SmartWrist đang kết nối. Kế hoạch dưới đây ưu tiên vật dụng dễ chuẩn bị và bằng chứng học thao tác.

Tài liệu bổ sung cho [lộ trình sản phẩm dữ liệu](DATA_PRODUCTS_ROADMAP.md). Các hướng dẫn bên dưới là bài thực hành bàn mẫu, cần người phụ trách xác nhận trước khi dùng trong sản xuất; không phải SOP được DENSO phê duyệt.

## 1. Quyết định phạm vi

Chọn hai công đoạn dùng chung vật dụng, biểu diễn được thao tác và kiến thức ra quyết định:

| Demo | Phòng ban đại diện | Công đoạn | Giá trị cần chứng minh |
|---|---|---|---|
| A | LOG | Soạn và kiểm đủ bộ linh kiện trước bàn giao | Chuyển kinh nghiệm kiểm tra mã, số lượng, thứ tự kiểm và xử lý bất thường thành hướng dẫn học được. |
| B | Sản xuất | Lắp bulông–long đen–đai ốc vào gá bằng tay | Chuyển cách bố trí đồ, phối hợp hai tay, giữ chi tiết và kiểm kết quả thành hướng dẫn có video/đối chiếu. |

Giả định dụng cụ sẵn có: bulông/đai ốc cùng ren, long đen, tấm gá có lỗ phù hợp, ba khay hoặc ba vùng dán nhãn, phiếu danh mục linh kiện. Chọn chi tiết đủ lớn để camera hiện tại nhìn rõ; đây không phải demo dung sai vi lắp ráp 2 mm.

Nếu chưa có gá: dùng tấm lỗ phù hợp hoặc bộ đồ chơi lắp ghép lớn. Ghi đúng tên vật dụng thực tế vào phiên bản bài thực hành; không gọi bài mô phỏng bàn mẫu là thao tác dây chuyền thật.

Không cần huấn luyện model thị giác nhận mọi lỗi để làm hai demo này. Người chuyên gia xác nhận bước/quyết định; AI hỗ trợ ghi, phân đoạn, truy xuất ảnh, đối chiếu thao tác. Nhận diện vật thể, đọc mã, đếm linh kiện hoặc tự kết luận thiếu đồ là chức năng bổ sung, chưa được chứng minh bởi bộ nhận diện động tác tay hiện tại.

### Danh sách chuẩn bị trong ngày đầu

| Vật dụng | Số lượng đề nghị | Mục đích / tiêu chí chọn |
|---|---:|---|
| Bulông M6 × khoảng 20–30 mm, đai ốc M6 và long đen lỗ phù hợp | 6 bộ cùng loại | Đủ làm lại nhiều lượt, thay đồ nhanh và chừa bộ mẫu; chọn đai ốc thường vặn tay trơn, thử khớp ren ngay khi mua. Chiều dài bulông phải vượt chiều dày gá + long đen + đai ốc. |
| Tấm/thanh gá có lỗ sẵn đủ lọt bulông M6 | 1–2 tấm | Chọn gá có thể tiếp cận hai mặt, cạnh nhẵn, đặt ổn định. Có thể dùng thanh góc đục lỗ sẵn; không cần khoan/gia công riêng. Kiểm tra cả bộ lắp được trước khi mua. |
| Long đen khác cỡ, nhìn phân biệt rõ | 2 chiếc | Tạo tình huống nhầm loại ở bài LOG; ghi rõ đây là mẫu gây nhầm chủ động. |
| Khay/hộp đang có | 3 vùng/khay | Nhãn “NGUỒN”, “ĐỦ BỘ”, “CHỜ KIỂM”; ngăn nhỏ hoặc ô đánh dấu cho từng loại. |
| Giấy A4/A3, băng dính giấy, bút đậm, thước | 1 bộ | Làm phiếu BOM, đánh dấu ô đặt đồ, bảng bước và nhãn dễ đọc trên camera. Thước phục vụ bố trí, không tự chứng minh calibration <2 mm. |
| Tấm lót bàn lì, màu tương phản với linh kiện | 1 tấm | Hạn chế phản chiếu và giúp thấy rõ đồ kim loại; thử trực tiếp bằng SmartCap. |
| Đèn bàn ánh sáng liên tục | 1 chiếc nếu bàn tối | Chiếu vùng thao tác, tránh bóng tay và chói kim loại. |
| Người đóng vai học viên | 1 người, tốt hơn là 2 | Thực sự thử làm theo SOP. Người thao tác mẫu và người mới nên khác nhau. |
| Điện thoại + giá đỡ, nếu sẵn có | Tùy chọn | Quay toàn cảnh/bản dự phòng có ghi nguồn rõ; không trộn camera này với timestamp SmartCap rồi gọi là đã đồng bộ. |

**Mua tối thiểu:** 6 bộ bulông–đai ốc–long đen, 1 gá lỗ sẵn phù hợp, 2 long đen khác cỡ. Hộp/khay, giấy/bút và ánh sáng có thể tận dụng. Không cần mua robot, dụng cụ siết điện hoặc thiết bị đo lực để hoàn thành demo học thao tác này.

Trước khi chốt đồ, thử đặt ba loại linh kiện trong khung hình SmartCap. Nếu QVGA không đủ nhìn điểm khác nhau, chọn chi tiết/mẫu phân biệt lớn hơn và điều chỉnh góc/ánh sáng. Không chọn bài phân biệt lỗi rất nhỏ mà camera không thể hiện được.

### Lịch 3 ngày

| Ngày | Việc người dùng chuẩn bị/thực hiện | Công việc phần mềm/nội dung ưu tiên | Điều kiện kết thúc ngày |
|---|---|---|---|
| Ngày 1 | Có vật dụng, bố trí bàn, thử lắp khớp, xác nhận 4 bước cho A/B; người hướng dẫn giải thích lý do và lỗi cần tránh. | Kiểm tra capture→publish, ghi role/reference đúng; hoàn thành SOP và note hai task. | Một phiên mẫu thật mỗi task, thấy rõ vật và hai tay, reference truy cập được. |
| Ngày 2 | Người mới làm trước học, xem SOP và làm lại; người đánh giá ghi checklist/timestamps. | Chọn ảnh/mốc video, hoàn thiện đối chiếu và gói nguồn/nhãn; kiểm đường mở session. | Hai case study có video thật, note, đầu ra vật lý và bảng kết quả; chỉ ghi số đã đo. |
| Ngày 3 | Diễn tập 6–8 phút ít nhất hai lượt, chuẩn bị người/vật dụng thay nhanh. | Kiểm links/download và bản phát lại offline, sửa lỗi chặn demo; đóng phiên bản dùng trình diễn. | Một lượt chạy sân khấu hoàn chỉnh, có phương án phát lại thật nếu mạng/camera lỗi. |

Đây là lịch thực hiện đề xuất, không phải cam kết mọi hạng mục phần mềm đã được triển khai. Nếu cuối ngày 1 chưa capture/publish ổn, ưu tiên bản ghi thật và SOP offline trước; không thêm phân loại lỗi tự động hoặc huấn luyện robot vào đường demo bắt buộc.

Kiểm tra kết nối ngày lập tài liệu: camera TCP, MQTT TCP và NTP đều phản hồi; dependencies được phát hiện. Bằng chứng tại `docs/layer1-layer3/demo-preflight.json`. Đây là kiểm tra kết nối, chưa chứng minh camera có hình rõ, bốn FSR/IMU hoạt động hoặc đạt tốc độ/đồng bộ yêu cầu.

## 2. Có thể học và huấn luyện robot ngay chưa?

| Đầu ra | Hiện tại | Điều kiện để được tuyên bố trong demo |
|---|---|---|
| Xem lại thao tác | Có video/keyframe và một phần phân tích từ pipeline đã có. | Mở đúng phiên, hình thấy rõ tay/chi tiết, nguồn đo được xác định. |
| Người mới tự học một công đoạn | Chưa xác nhận chỉ bằng video/DTW. Thiếu tri thức vì sao, tiêu chí đầu ra, thao tác bất thường và đánh giá người học. | Người chưa được hướng dẫn miệng đọc SOP/xem mẫu, thực hiện lại; người đánh giá kiểm kết quả và ghi số gợi ý cần hỗ trợ. |
| Dữ liệu cho mô hình nhận diện pha/thao tác | Có thể xây dựng từ video và nhãn được duyệt. | Gán nhãn thật, task/version, ground truth, tách người/episode cho đánh giá. Vài phiên demo chỉ đủ kiểm tra đường dữ liệu, chưa đủ khẳng định tổng quát hóa. |
| Dataset imitation learning điều khiển robot | **Chưa**. Thiếu robot action/teleop đã xác thực và biến đổi tọa độ/hiệu chuẩn. | Ghi được observation và robot commands cùng thời gian, frame/unit/calibration, loader đọc được và baseline được đánh giá. Đổi đuôi file sang HDF5/MCAP không giải quyết việc thiếu action. |
| Robot làm được việc | Chưa có bằng chứng. | Có robot/simulator adapter, policy và phép thử thành công độc lập. Mô phỏng phải ghi rõ là mô phỏng; replay video/trajectory không phải robot học được. |

Thông điệp trình bày: “Một lần ghi tạo tài liệu học thao tác và dữ liệu quan sát có nguồn gốc để phát triển mô hình. Chúng tôi đã/chưa kiểm chứng khả năng học bằng bài thực hành sau đây. Nhánh điều khiển robot có hợp đồng dữ liệu và các điều kiện còn cần bổ sung.” Chỉ dùng chữ “đã” khi có bằng chứng tương ứng.

## 3. Demo A — LOG: soạn và kiểm đủ bộ

### Vật dụng và kết quả đúng

- Một phiếu BOM bài mẫu: 1 bulông loại A, 1 long đen phù hợp, 1 đai ốc cùng ren. Đây là cấu hình bài thực hành, không phải BOM sản phẩm DENSO.
- Khay nguồn, khay bộ đã soạn, khay chờ xử lý bất thường; đánh dấu ba vị trí để dễ nhìn và kiểm thiếu.
- Một mẫu gây nhầm nhìn thấy được, ví dụ long đen khác kích thước. Không dùng lỗi cần đo chính xác khi chưa có dụng cụ đo.
- Đầu ra đạt: đúng loại theo mẫu/phiếu, đủ số lượng, từng vị trí đúng, không có vật lạ; mẫu không chắc chắn nằm trong vùng chờ xử lý.

### SOP để chuyên gia bổ sung và duyệt

| Bước | Người học làm gì | Kinh nghiệm cần ghi lại | Bằng chứng/video cần lấy |
|---|---|---|---|
| A1 | Đọc phiên bản phiếu và nhìn mẫu chuẩn trước khi lấy đồ. | Vì sao không lấy theo trí nhớ? Khi nào phải dừng để hỏi? | Phiếu/mẫu chuẩn và lời giải thích đã ghi thành note. |
| A2 | Lấy bulông, long đen, đai ốc theo thứ tự cố định; đặt mỗi loại vào ô riêng. | Một ô/một loại giúp thấy ngay thiếu; tránh che khuất linh kiện. | Tay lấy và đặt; cả khay nằm trong khung hình. |
| A3 | Đối chiếu từng ô với BOM/mẫu. | Điểm dễ nhầm và dấu hiệu nhận biết; không tự suy đoán khi mã/kích thước không rõ. | Keyframe trước và sau kiểm, ghi rõ ai xác nhận đúng/sai. |
| A4 | Tách mẫu nghi ngờ, kiểm lại bộ và chuyển sang khay hoàn tất. | Tại sao phải tách riêng, không để lẫn rồi xử lý sau? | Hành động tách/chuyển và lý do quyết định. |

Các nội dung ở cột kinh nghiệm là câu hỏi để khai thác chuyên gia, không phải lời chuyên gia đã nói. Chỉ đánh dấu approved sau khi người có chuyên môn xác nhận.

### Thử nghiệm

1. Quay 1–3 lượt người hướng dẫn thực hiện chuẩn; lưu nguyên video và note. Nếu người hướng dẫn không phải chuyên gia DENSO, ghi “người hướng dẫn bài mẫu”.
2. Người mới thực hiện lượt đầu với phiếu công việc tối thiểu. Ghi kết quả và số lần cần hỏi, không dàn dựng lỗi rồi gọi là lỗi tự nhiên.
3. Cho người mới xem SOP/micro-clip đã duyệt; thực hiện lại với bộ vật dụng được xáo vị trí hoặc mẫu nghi ngờ khác tương đương.
4. Người đánh giá kiểm: đúng bộ, số linh kiện thiếu/thừa/nhầm, bỏ sót kiểm, số gợi ý miệng, thời gian thao tác thực.
5. Có thể quay riêng một “tình huống lỗi chủ động: thiếu long đen”. Nhãn phải nói rõ lỗi được dàn dựng để kiểm chức năng xem lại; không trộn với kết quả học tự nhiên.

Điểm trình diễn tốt: người xem mở bước A3, thấy keyframe, biết dấu hiệu nào phải kiểm và vì sao phải tách mẫu không chắc chắn. Đây là tri thức ra quyết định, vượt khỏi việc chỉ ghi quỹ đạo tay.

## 4. Demo B — sản xuất: lắp bộ bằng tay

### Vật dụng và kết quả đúng

Sử dụng chính bộ A đã kiểm, cùng gá/tấm lỗ phù hợp. Lắp theo bản vẽ bài mẫu được người hướng dẫn xác nhận (ví dụ bulông qua tấm, long đen và đai ốc phía còn lại). Không tự coi thứ tự này đúng cho mọi sản phẩm. Chỉ vặn bằng tay đến trạng thái quy định của bài mẫu; không đặt mục tiêu lực siết hoặc mô-men vì chưa có cảm biến/hiệu chuẩn tương ứng.

Đầu ra đạt: đủ chi tiết đúng vị trí, không lệch/bắt chéo ren, lắp được nhẹ nhàng bằng tay, gá không bị xê dịch quá vùng quy định. Nếu thấy cứng bất thường, dừng và kiểm lại. Người hướng dẫn xác nhận tiêu chí bằng vật mẫu, không suy từ nhãn ASSEMBLY của AI.

### SOP để chuyên gia bổ sung và duyệt

| Bước | Người học làm gì | Kinh nghiệm cần ghi lại | Bằng chứng cần lấy |
|---|---|---|---|
| B1 | Bố trí bộ đã kiểm trong vùng lấy, cố định/giữ gá. | Vì sao cách bố trí giúp tránh tìm kiếm và đổi tay thừa? | Ảnh bàn mẫu, vị trí bắt đầu giống nhau giữa các lượt. |
| B2 | Một tay giữ gá, tay kia đưa bulông qua lỗ. | Chọn tay giữ/tay thao tác theo thuận tay và yêu cầu task; không áp một kiểu cho tất cả. | Thấy cả hai tay và điểm tiếp xúc. |
| B3 | Đặt long đen, đưa đai ốc đúng trục; bắt ren nhẹ theo hướng dẫn. | Dấu hiệu ren chưa vào; khi nào dừng và làm lại thay vì tăng lực? | Clip cận thao tác, note về cảm giác/điểm nhìn. |
| B4 | Hoàn thành vặn bằng tay tới tiêu chí bài mẫu và kiểm đầu ra. | Kiểm đủ chi tiết và vị trí; không đánh giá hoàn tất chỉ từ thời gian nhanh. | Keyframe sản phẩm, checklist người đánh giá. |

### Thử nghiệm

- Quay người hướng dẫn và người mới với cùng gá, bố trí và ánh sáng. Ghi người thuận tay nào; khác chiến lược phối hợp tay chưa chắc là thao tác sai.
- Đánh giá: đầu ra đạt/chưa đạt; số lần phải tháo/lắp lại; số lần hỏi; thời gian từng bước đã đánh dấu; quãng chuyển động trong ảnh chỉ là pixel/normalized.
- DTW hiện so chuỗi nhãn động tác và thời lượng, không phải phép đo chính xác khoảng cách robot. Chỉ nói “đoạn cần xem lại”, không nói “AI chứng minh thao tác sai” khi chưa có người xác nhận.
- FSR chỉ dùng để cho thấy tín hiệu ADC thay đổi theo tiếp xúc của kênh hoạt động; không quy ra Newton, mô-men, lực toàn bàn tay hay lực lên chi tiết.
- Với kênh hỏng/IMU thiếu: đánh dấu thiếu rõ ràng. Demo vẫn đánh giá học thao tác dựa vào video/checklist, không tuyên bố đã nghiệm thu toàn bộ phần cứng.

## 5. Bộ đầu ra tối thiểu của mỗi công đoạn

### Gói người học

1. Một SOP 1 trang: mục tiêu, dụng cụ, đầu ra đạt, 4 bước, lý do/mẹo và tình huống cần dừng.
2. Một video mẫu thật và 4 mốc thời gian/keyframe ứng với bước. Clip cắt theo bước là ưu tiên; nếu chưa có exporter clip, dùng video nguồn và mốc seek chính xác, ghi rõ cách cung cấp.
3. Phiếu tự kiểm 4–6 tiêu chí; người mới thực hiện lại mà không nghe hướng dẫn miệng bổ sung.
4. Bản đối chiếu lần đầu/lần sau với evidence: time range, lỗi người đánh giá xác nhận, số gợi ý. Không tạo số % cải thiện trước khi đo.

### Gói máy học

1. Video/ảnh nguồn, timestamp, landmarks hai tay/confidence và ADC/IMU nếu có, kèm validity/source.
2. `task_id`, `department_label`, phiên bản SOP, role thực, reference session, người gán nhãn, step timestamps và outcome do người đánh giá ghi.
3. Nhãn bước A1–A4/B1–B4 do con người duyệt; nhãn REACH/GRAB hiện tại được giữ riêng. Không đồng nhất GRAB với “đã lấy đúng linh kiện”.
4. Manifest/README ghi mục đích sử dụng: **observation + reviewed task labels**; `robot_action_available=false` và `robot_policy_training_ready=false` cho đến khi có action thật.
5. Tách episode/người giữa train và test; không lấy frame liền kề của cùng video làm “test độc lập”. Nếu chỉ có vài phiên, dùng để smoke-test data loader, không báo accuracy đại diện nhà máy.

Máy có thể học bài toán nhận diện bước khi dataset đủ nhãn/chất lượng/số lượng. Đó là một bài toán khác với học điều khiển robot. Nếu ban tổ chức bắt buộc robot phải học và làm được ngay, cần có robot/teleop hoặc simulator đã tích hợp; hiện chưa có bằng chứng đáp ứng yêu cầu đó.

## 6. Lệnh có thể dùng với pipeline hiện tại

Chạy từ root dự án. Backend/broker/NTP phải hoạt động theo RUNBOOK. Không mở serial/flash/reset trong lúc đang thu camera. Cổng USB gần nhất trong nhật ký là SmartCap COM5 và SmartWrist COM7; kiểm lại trước thao tác phần cứng.

```powershell
. .\deployment\hardware.ps1
.\.venv\Scripts\python.exe -B ai\hardware\preflight.py --output docs\layer1-layer3\demo-preflight.json
```

Preflight chỉ kiểm kết nối/dependency; chưa chứng minh hình ảnh/sensor đạt chất lượng. Dừng các phiên dashboard khác trước khi chạy CLI; mỗi thời điểm chỉ một bộ thu camera.

Quay reference cho A (sau đó làm tương tự cho B):

```powershell
.\.venv\Scripts\python.exe -B ai\hardware\record_hardware.py --headless --duration-s 60 --process --publish --role expert
```

Lưu chính xác đường dẫn phiên được CLI in ra. Mỗi công đoạn phải có reference riêng. Dùng đường dẫn thật thay cho placeholder sau:

```powershell
$demoExpertSession = 'D:\MyProject\Denso2\smartwear-ai-software\ai\generated_data\sessions\<THU_MUC_EXPERT_A_THAT>'
.\.venv\Scripts\python.exe -B ai\hardware\record_hardware.py --headless --duration-s 60 --process --publish --role worker --expert-session $demoExpertSession
```

Khoảng capture 60 giây không phải cycle time. Ghi timestamp bắt đầu/kết thúc thao tác thực; khoảng chờ đầu/cuối không được cộng vào thời gian công đoạn.

Dashboard hiện chuyển role/task/version và reference đã duyệt tới AI; worker chọn đúng task/version và review revision của expert. Chế độ thử DEMO phải chọn rõ trong giao diện. CLI trên vẫn dùng được nhưng chưa cung cấp đầy đủ metadata/review như workflow dashboard mới.

UI có form note/SOP theo bước, start/end/keyframe, outcome và số gợi ý; người hướng dẫn vẫn phải tự xem và duyệt bằng chứng. Khi trình bày phải nói rõ phần này được người duyệt, không nói AI tự trích xuất mọi kiến thức.

## 7. Phiếu evidence để điền sau mỗi lượt

Không điền trước kết quả. Sao chép một hàng cho mỗi lượt; các chỉ số do người xem ghi có `source=human_review`.

| Task | Người/role | Lượt | Session ID/đường dẫn | Reference | Start–end thao tác | Đầu ra đạt? | Lỗi đã xác nhận | Số gợi ý | Reviewer |
|---|---|---|---|---|---|---|---|---|---|
| A/B | Chưa ghi | Trước/sau học | Chưa ghi | Chưa chọn | Chưa đánh dấu | Chưa đánh giá | Chưa đánh giá | Chưa đo | Chưa duyệt |

Theo dõi thêm thời gian từ lúc dừng quay đến khi artifact sẵn sàng, độ rõ video và các modality bị thiếu. Với ít người/lượt, kết quả là case study tại bàn demo; có thể có hiệu ứng quen bài ở lượt hai, chưa chứng minh hiệu quả đào tạo trên diện rộng.

## 8. Kịch bản sân khấu 6–8 phút

| Thời gian | Hành động trình diễn | Bằng chứng hiện lên |
|---|---|---|
| 0:00–0:40 | Nêu vấn đề: chuyên gia nhiều phòng ban, kinh nghiệm nằm cả trong động tác lẫn lý do quyết định. | Hai task LOG và sản xuất, cùng cấu trúc step/evidence/note/outcome. |
| 0:40–1:40 | Mở mẫu A đã quay thật; chọn bước kiểm bộ, đọc dấu hiệu cần kiểm và xử lý bất thường. | Video đúng session, note được người hướng dẫn duyệt, checklist. |
| 1:40–2:40 | Một người mới dùng hướng dẫn để kiểm bộ trước mặt người xem. | Kết quả vật lý và phiếu đánh giá; không nhắc đáp án. |
| 2:40–4:10 | Demo B: giữ gá/lắp một chu kỳ 30–60 giây; hiển thị live tay và ADC khi có. | Camera live thật, nhận diện hai tay; trạng thái thiếu sensor nếu có. |
| 4:10–5:10 | Mở phiên B đã xử lý từ buổi chuẩn bị và chỉ một đoạn cần sửa đã được xác nhận. | Expert/worker session khác nhau, ảnh/phase/time và ghi chú “vì sao”. |
| 5:10–6:10 | Mở gói người học và một mẫu dữ liệu máy; chỉ nguồn timestamp/nhãn/validity. | Người học thấy hướng dẫn; kỹ sư thấy dữ liệu có schema/provenance. |
| 6:10–7:00 | Nêu kết quả đo thực tế trước/sau, giới hạn và bước mở rộng. | Evidence thật; observation-only/robot-action status rõ. |
| 7:00–8:00 | Trả lời câu hỏi hoặc mở lại đoạn người xem chọn. | Truy xuất được video/step/note cụ thể. |

Không chờ toàn bộ xử lý AI trên sân khấu nếu chưa benchmark đủ nhanh. Có thể quay live và dùng phiên đã quay/xử lý trước để trình diễn phần sau, nhưng ghi rõ phiên nào là live, phiên nào phát lại. Video dự phòng phải là bản thu thật và có session ID; không giả replay thành live.

## 9. Thứ tự công việc khi thời gian ít

Ưu tiên theo tác động đến khả năng chứng minh, không dựa vào lượng tính năng:

1. Chốt vật dụng, góc quay, hai task và người hướng dẫn. Quay một clip thử có đủ tay/chi tiết; ánh sáng và khung hình quan trọng hơn thêm biểu đồ.
2. Điền và duyệt SOP 4 bước cho mỗi task, đặc biệt cột “vì sao”/“khi nào dừng”. Đây là phần số hóa kinh nghiệm cần thể hiện.
3. Thu các reference thật và các lượt người mới; nối chính xác reference qua CLI. Chọn một case study có đủ video, note và phiếu đầu ra.
4. Đánh dấu time range thật, chọn keyframe dễ hiểu; chuẩn bị clip hoặc seek video và bản SOP có thể mở offline.
5. Chạy thử kịch bản sân khấu bằng đồng hồ; kiểm links/API/video, lưu bản phát lại thật dự phòng. Không thay firmware đang ổn định sát buổi demo chỉ để đuổi KPI chưa kiểm chứng.
6. Chỉ sau khi 1–5 ổn, bổ sung UI expert/reference và exporter dataset. Không để phần robot chưa có hardware/action chiếm hết thời gian hoàn thiện trải nghiệm người học.

## 10. Mở rộng sang nhiều phòng ban

Đơn vị tri thức chung là `task → version → step → observation → decision → rationale → outcome`, không phải chỉ chuỗi cử động tay. Mỗi bộ phận định nghĩa tiêu chí thành công khác nhau; vì thế không so DTW giữa hai công việc không liên quan.

- LOG: phiếu/yêu cầu → kiểm đủ/đúng → quyết định bàn giao hay chờ xử lý.
- Sản xuất: thao tác → điều kiện lắp đúng → lỗi và cách phục hồi.
- MA/PE và bộ phận khác: cần làm rõ nghiệp vụ cụ thể với DENSO; không tự suy diễn ý nghĩa chữ viết tắt. Có thể bổ sung sơ đồ, màn hình máy, tài liệu, âm thanh hoặc log thay vì yêu cầu mọi kinh nghiệm đều đo được bằng vòng tay.

Hai demo chứng minh cách lưu/truy xuất/học một đơn vị tri thức áp dụng được ở hai bối cảnh. Chúng chưa chứng minh hệ thống hiểu tự động mọi nghiệp vụ trong nhà máy.

## 11. Cách trình bày để có sức thuyết phục

Chưa có rubric chấm điểm chính thức nên không thể bảo đảm điểm cao. Bằng chứng mạnh nên tập trung vào:

- Một người mới làm được công việc nhờ tài liệu, với kết quả vật lý được người có chuyên môn xác nhận.
- Một lý do/mẹo quan trọng của chuyên gia được lưu đúng bước và tìm lại nhanh.
- Một sai lệch thật được truy về đoạn video, người đánh giá giải thích được cách sửa.
- Cùng cấu trúc tri thức dùng được ở hai phòng ban, có tiêu chí đầu ra khác nhau.
- Chỉ số trước/sau, nguồn đo và phần còn thiếu được thể hiện trung thực.

Câu trả lời ngắn cho ban giám khảo về robot: “Hiện demo thu video, cảm biến và nhãn bước đã duyệt để làm dữ liệu quan sát cho mô hình. Để huấn luyện policy điều khiển robot, chúng tôi cần bổ sung action từ robot/teleoperation, hiệu chuẩn và kiểm định đồng bộ; chúng tôi chưa gọi các file hiện tại là robot-ready.”

## 12. Definition of Done của buổi demo

- [ ] Vật dụng và SOP hai công đoạn được người hướng dẫn duyệt.
- [ ] Mỗi công đoạn có ít nhất một reference thật, role rõ và một lượt người mới thực hiện.
- [ ] Mỗi bước có hướng dẫn, lý do/điểm kiểm, mốc video hoặc keyframe.
- [ ] Một người mới thử học không cần hỗ trợ miệng; ghi cả trường hợp thất bại và số lần cần gợi ý.
- [ ] Session worker trỏ đúng expert cùng task; không fallback DEMO trong bài thực nghiệm.
- [ ] Kết quả đầu ra, thời gian thao tác và phần thiếu dữ liệu được ghi thật.
- [ ] Gói dữ liệu máy có nguồn/nhãn/validity và ghi rõ chưa có robot action.
- [ ] Kịch bản 6–8 phút đã diễn tập; bản phát lại thật được ghi nhãn và mở offline được.
- [ ] Không công bố N/mm/mô-men, tự phát hiện lỗi, tỷ lệ cải thiện hoặc robot học thành công khi chưa có phép đo tương ứng.
