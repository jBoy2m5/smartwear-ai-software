# SmartWear AI — Kịch bản video demo 120 giây

Ngày soạn: 09/10/2026. Đối tượng: Ban giám khảo DENSO Factory Hacks 2026; định hướng A1 số hóa bí quyết và H1 dữ liệu thao tác cho nghiên cứu robot theo brief của nhóm.

## Thông điệp và quy ước bằng chứng

**Một lượt thao tác → video và cảm biến có nguồn gốc → hướng dẫn được người có chuyên môn duyệt → dữ liệu quan sát có thể kiểm tra lại.**

Kịch bản dùng bài lắp bulông–long đen–đai ốc bằng tay đã có trong kế hoạch demo. Chọn chi tiết đủ lớn để camera QVGA thấy rõ. Có thể nêu linh kiện 10 mm như yêu cầu khó của nhà máy, nhưng chưa trình bày nguyên mẫu đã nghiệm thu thao tác 10 mm.

Các số dưới đây lấy từ tài liệu nội bộ, là kết quả của từng lượt thử cụ thể:

- `IMPROVEMENTS_20261009.md`: lượt `hardware_20261009_114208_401398_b97nj0sz` có 315 JPEG, 312 inferred frames, 0 dropped_for_inference và 3 ảnh còn trong queue khi dừng; AI 15,59 FPS, wrist 49,96 Hz; inference p95 50,877 ms. Chưa là benchmark tăng tốc có kiểm soát.
- `layer1-layer3/VERIFICATION-20261007.md`: lượt `hardware_20261007_142254_436256_i1uwuwl2` ghép 1.061/1.063 frame, tương đương 99,81%; p95 9 ms, max 10 ms. Phiên này không thấy tay, chỉ dùng làm bằng chứng ghép dữ liệu, không dùng làm mẫu thao tác chuyên gia.
- `DATA_PRODUCTS_REVIEW_20261007.md`: episode `3fcfd3e0cc9f8742` từ phiên `MEASURED_hardware_20261007_150625_216050_uk5sxhc9` có 1.555 frames, 12 artifacts/13 mục checksum hợp lệ; một lượt tạo gói mất 48,703 giây. Phiên legacy này có `learner_ready=false`, `robot_ready=false`.

Các số từ phiên khác nhau phải nằm trong thẻ bằng chứng riêng, có ngày và session ID; không chèn thành số LIVE của phiên đang quay. Chỉ dùng chữ LIVE khi hình và số đang đến từ capture hiện tại. Bản ghi thật phát lại ghi REPLAY; bộ mô phỏng ghi SIMULATED.

## Timeline bản chính — 120 giây

Lời thoại khoảng 280 từ, cần đọc thử với đồng hồ và điều chỉnh nhịp theo người dẫn. Cột thao tác và overlay là chỉ dẫn sản xuất, không đọc thành lời.

| Thời gian (giây) | Phân cảnh / Góc quay (Visual) | Thao tác trên thiết bị / Màn hình (Action) | Lời thoại thuyết minh (Voiceover/Pitch) | Dữ liệu & Bằng chứng kỹ thuật hiển thị (Data Overlay) |
| --- | --- | --- | --- | --- |
| 00–08 | **Cận cảnh:** người hướng dẫn đặt long đen, bắt ren. Cắt sang người mới dừng lại kiểm. Âm thanh thao tác thật; nhạc nền nhỏ. | Đặt sản phẩm và phiếu hướng dẫn cạnh nhau, thể hiện khoảnh khắc phải hỏi lại. Nếu diễn tình huống, ghi nhãn minh họa. | “Bí quyết nằm trong cách giữ chi tiết, bắt ren và biết khi nào phải dừng.” | “Bí quyết ngầm → khó truyền đạt”; không gắn số thiệt hại chưa đo. |
| 08–16 | **Góc rộng → cận cảnh:** cùng bàn thao tác, SmartCap trên trán và wrist/FSR trên tay phải. SFX click nhẹ khi gọi tên thiết bị. | Người thao tác xoay tay để thấy vị trí camera, wrist và các FSR; dây được cố định gọn. | “SmartWear ghi góc nhìn người thao tác và tín hiệu cổ tay ngay trong lúc làm việc.” | “ESP32-CAM / ESP32-WROOM + 4 kênh FSR”; “MPU6050: hiển thị tình trạng thực”. |
| 16–25 | **Macro thiết bị + motion graphic** ba tầng, mỗi tầng sáng lần lượt. Nếu có, chèn cảnh cân và BOM thật. | Cho thấy đường camera → gateway và wrist → MQTT, sau đó hội tụ vào AI. | “Dữ liệu đi qua ba tầng: thiết bị, gateway đồng bộ và AI hỗ trợ phân tích.” | “L1 Thu → L2 Ghép thời gian → L3 Phân tích”. Chỉ thêm “<40 g” hoặc “<1,5 triệu đồng” sau khi đo/có BOM đúng phạm vi. |
| 25–35 | **Split-screen:** trái FPV, phải screen record dashboard cùng một phiên. Giữ cảnh đủ lâu để đọc. | Bắt đầu capture; người thao tác đưa tay vào khung hình, lấy một chi tiết. | “Bên trái là hình từ mũ. Bên phải là dữ liệu của cùng phiên đang được ghi.” | “LIVE — session [ID]” hoặc “REPLAY — session [ID]”; kích thước ảnh và tốc độ lấy từ phiên tương ứng. |
| 35–47 | **Cận bàn tay**, cắt khớp nhịp với đồ thị thật. Không dùng đồ thị dựng để giả phản hồi. | Nhấn rồi nhả từng FSR có phản hồi; giữ đủ 1–2 giây mỗi lần. Chỉ bấm vào vùng cảm biến đã xác định. | “Nhấn và nhả tạo thay đổi ADC. Kênh thiếu và IMU chưa có dữ liệu được đánh dấu rõ.” | Bốn kênh “FSR 0–3, ADC raw”. “IMU: unavailable” nếu thiếu. Nếu dashboard chỉ có giá trị số, giữ số thật; đồ thị bổ sung phải dựng từ JSONL cùng phiên. |
| 47–60 | **Screen record cận metadata** + motion graphic hai timeline camera/wrist; nối cặp gần nhất. SFX tick khi xuất hiện cặp. | Hiện delta/missing từ capture thật. Sau đó cắt hẳn sang thẻ bằng chứng lịch sử, không đặt trong khung LIVE. | “Gateway ghép mẫu gần nhất trong cửa sổ mười mili giây. Một lượt kiểm tra đạt 99,81 phần trăm khung hình được ghép.” | Live: `Δt = [giá trị thật] ms`, `MATCH/MISSING`. Thẻ lịch sử: “07/10 · 1.061/1.063 · p95 9 ms · max 10 ms”, session rút gọn `142254…i1uwuwl2`. Chú thích “Độ lệch timestamp ghép; chưa đo sai số clock”. |
| 60–70 | **Screen record:** bấm kết thúc, chuyển sang kết quả đã xử lý. Zoom timeline và keyframe. SFX chuyển cảnh ngắn. | Hiện các nhãn thực có trong phiên. Nếu phải đợi xử lý, cắt dựng và ghi “Sau xử lý”. | “AI đề xuất các pha tiếp cận, kẹp, lắp và nhả; mỗi đoạn có hình để kiểm tra lại.” | “Nhãn AI/heuristic — cần duyệt”; chỉ hiển thị REACH/GRAB/ASSEMBLY/OPEN nếu kết quả thật có nhãn đó. |
| 70–82 | **Hai video cạnh nhau:** reference và worker cùng task; đánh dấu một đoạn cần xem lại. | Chọn reference đã duyệt và kết quả DTW thật. Seek về đoạn chênh lệch, phát 2–3 giây. | “DTW đối chiếu chuỗi thao tác với mẫu tham chiếu, giúp tìm đoạn cần xem lại. Người đánh giá xác nhận nguyên nhân.” | Hai session ID, reference/review revision, chênh thời lượng thật; “MUDA candidate”. Không gọi DTW hiện tại là đo quỹ đạo 3D hoặc bộ phát hiện rung tay đã nghiệm thu. |
| 82–95 | **Cận màn hình:** SOP theo bước, video/keyframe và ghi chú “vì sao”. Cắt sang nút tạo/tải gói. | Mở một ghi chú do người hướng dẫn viết và duyệt. Bấm tạo gói; chuyển tới gói đã hoàn tất, ghi rõ thời gian thực. | “Hướng dẫn nối từng bước với video và lý do của người hướng dẫn. Gói dữ liệu có thể tải về để xem lại.” | `SOP: approved/draft` theo dữ liệu. Nếu dùng benchmark có sẵn: thẻ riêng “Gói kỹ thuật legacy: 48,703 s / 1 lượt; SOP chưa duyệt”, không nhận là SOP learner-ready tạo trong thời gian này. |
| 95–108 | **Screen record:** mở manifest, HDF5/MCAP và báo cáo kiểm checksum; motion graphic hướng sang robot dưới dạng lộ trình. | Mở gói quan sát đã kiểm; highlight timestamps, validity và source. Không chỉ vào file robot rỗng rồi nói đã sẵn sàng học. | “Đầu ra máy giữ quan sát, timestamp và trạng thái hợp lệ. Huấn luyện robot cần thêm lệnh robot và hiệu chuẩn.” | “OBSERVATION-ONLY”; `robot_policy_training_ready=false`. Thẻ episode `3fcfd3e0cc9f8742`: “1.555 frames · 12 artifacts · 13 checksum hợp lệ”. MCAP JSON observations, không gắn nhãn ROS2 native trajectory + force. |
| 108–120 | **Góc rộng:** người hướng dẫn và người học bên sản phẩm; chốt bằng màn hình SOP và logo. Nhạc nâng nhẹ rồi dừng. | Người học chỉ bước vừa xem; người đánh giá kiểm sản phẩm. Nếu chưa có thực nghiệm, dùng cảnh giới thiệu pilot thay cảnh tuyên bố kết quả. | “Bước tiếp theo: thử trên một công đoạn, đo thời gian, lỗi và số lần cần hỗ trợ. Chúng tôi tìm đối tác cùng kiểm chứng.” | “Pilot: reference → trước học → SOP → sau học”; “Đo thời gian + lỗi + số gợi ý”. Không hiển thị giảm 50% hoặc ROI <6 tháng như kết quả đã đạt. |

## Điều kiện để dùng các tuyên bố trong brief

| Tuyên bố đề xuất | Cách sử dụng với nguyên mẫu hiện tại | Bằng chứng cần có để công bố đạt |
| --- | --- | --- |
| SmartCap <40 g | Bỏ số khỏi bản chính; có thể ghi mục tiêu thiết kế trong slide phụ. | Cảnh cân cụm đeo thực, ghi rõ có gồm nguồn/dây/giá đỡ không. |
| Chi phí <1.500.000 VNĐ | Dùng “mục tiêu BOM” nếu nhóm vẫn chọn mục tiêu này. | BOM có giá/ngày, số lượng, phạm vi thiết bị; nói rõ gateway/laptop và lắp ráp có được tính không. |
| Linh kiện 10 mm | Dùng làm bối cảnh yêu cầu cần giải quyết. | Video vùng tiếp xúc đủ rõ và nghiệm thu tác vụ 10 mm thực. |
| 50 Hz | Nói “49,96 Hz trong lượt thử được ghi nhận” khi dùng số đã có. | Sample count/timestamps/session cụ thể; không gắn vào phiên live khác. |
| Delta-T <10 ms [PASS] | Đổi thành “ghép trong ±10 ms”; biên 10 ms được code chấp nhận. | Delta và coverage từng phiên. Kiểm clock accuracy là phép đo riêng. |
| Bốn cột lực + MPU6050 | Hiện ADC của kênh thực; kênh thiếu/IMU unavailable hiện đúng trạng thái. | Dữ liệu mới xác minh từng kênh và IMU; Newton cần hiệu chuẩn. |
| DTW phát hiện rung tay/động tác thừa | Nói “gợi ý đoạn khác mẫu để người đánh giá xem lại”. | Tính năng/feature rung tay và benchmark độc lập nếu muốn tuyên bố phát hiện rung. |
| SOP trong tích tắc hoặc <15 phút | Quay thời gian xử lý thực; tách sinh artifact khỏi người viết/duyệt tri thức. | Start/end, input size, artifact readiness và trạng thái review. Một benchmark gói kỹ thuật chưa chứng minh toàn bộ SOP learner-ready. |
| ROSbag trajectory + force sẵn sàng robot | Hiện HDF5/MCAP observation đã kiểm, readiness false. | Robot action/state, calibration, adapter ROS2 đúng schema và phép thử học/điều khiển. File `.db3` đơn thuần không chứng minh điều đó. |
| Giảm 50% thời gian đào tạo | Chỉ dùng “mục tiêu pilot, chưa kiểm chứng” nếu cần nêu. | Người học thật, thời gian đạt chuẩn, lỗi, số gợi ý và điều kiện/nhóm so sánh phù hợp. Cycle time một thao tác không phải tổng thời gian đào tạo. |
| Hoàn vốn <6 tháng | Để trong mô hình kinh doanh giả định, không đọc như kết quả demo. | Chi phí triển khai/vận hành, lợi ích đo được và mô hình dòng tiền có giả định rõ. |

## Chỉ dẫn đạo diễn và chuẩn bị

1. Quay tổng thể bằng điện thoại/máy quay ngoài; FPV lấy trực tiếp từ bản ghi SmartCap. Giữ overlay chữ lớn, tối đa ba chỉ số chính mỗi cảnh; session ID đầy đủ đặt trong appendix/video description.
2. Quay bàn tay và màn hình cùng lượt nếu nói có tương quan lực. Với video dựng, căn theo timestamp hoặc dấu mốc thật; nếu chỉ minh họa sơ đồ đồng bộ, ghi “Sơ đồ minh họa”.
3. Không mở thêm `/stream` trên browser để screen record. Quay màn hình preview backend hiện có; chỉ một consumer camera. Đóng Serial Monitor trước capture.
4. Chuẩn bị trước reference và worker đúng task/version, ghi chú chuyên gia và review thật. Nếu chưa có, phần 70–95 giây dùng kết quả kỹ thuật hiện có với nhãn “mẫu DEMO / SOP draft”; thay lời thoại bằng: “Đây là đối chiếu với mẫu DEMO. Trong pilot, người hướng dẫn sẽ ghi mẫu và duyệt nội dung trước khi dùng đào tạo.” Không gọi phiên legacy là reference được chứng nhận.
5. Screen record các thao tác mở session, seek, SOP, tải gói trước buổi dựng. Các bước xử lý dài được cắt dựng với nhãn “Sau xử lý”; giữ duration thật, không thêm stopwatch giả.
6. Chỉ dùng SFX nhẹ tại chuyển tầng, ghép timestamp và hoàn tất tải. Không thêm âm thanh “PASS” vào cảnh thiếu dữ liệu. Motion graphic không được giống widget đo live nếu chỉ minh họa.
7. Khóa bản video sau một lượt đọc thử 120 giây; kiểm từng số với session nguồn. Phần mềm build/API đã được kiểm nhưng bố cục/thao tác UI cần quay và kiểm trực tiếp trước khi trình chiếu.

## Fallback khi demo trực tiếp hoặc không quay được mạch

### A. Mạch đã có bản thu thật nhưng live lỗi

Ưu tiên phát lại bản thu thật đã chuẩn bị, ghi nhãn **REPLAY — bản thu thật — ngày/session** trong toàn bộ khung hình. Dùng cùng timeline; thay câu 25–35 giây bằng: “Đây là bản thu thật đã lưu; hình và dữ liệu cùng một phiên.”

Chuẩn bị video cuối, gói ZIP đã giải nén, SOP HTML và báo cáo JSON trên ổ cục bộ. Kiểm mở được khi mất mạng. Tránh chạy thêm raw collector trong lúc dashboard đang capture.

Trong live demo 120 giây, 25–60 giây dành cho capture; từ giây 60 dùng phiên đã xử lý trước và nói rõ chuyển phiên. Không phụ thuộc việc AI/export hoàn tất trong 35 giây. Nếu live ngừng ảnh, chuyển replay ở ranh giới phân cảnh gần nhất, không giữ badge LIVE.

### B. Chỉ có Mock Hardware + Webcam

Mục đích: trình diễn giao diện và đường xử lý phần mềm. Không dùng bản này làm bằng chứng cảm biến/đồng bộ phần cứng. Các dịch vụ có sẵn trong repo không mặc nhiên tạo thành một bộ mô phỏng hardware end-to-end.

1. Giữ webcam và người thao tác trong góc rộng; badge cố định **WEBCAM + SIMULATED SENSORS**. Lời mở: “Bản này minh họa luồng phần mềm bằng webcam và cảm biến mô phỏng.”
2. Với backend hiện có, capture mode hardware đang được script khởi động đặt tự động. Muốn thử webcam/DEMO, kết thúc mọi capture và dừng backend trước; dùng cấu hình webcam/DEMO đã kiểm với mã hiện tại, không chạy `start-backend.ps1` rồi giả định đã đổi mode. Quay thử thành công trước ngày demo.
3. Backend có websocket simulator được tài liệu mô tả tại `ws://127.0.0.1:8000/ws/live-stream?simulate=true`. Xác minh dashboard cần dùng có tiêu thụ đúng endpoint/schema trước khi quay; simulator telemetry này không chứng minh ring buffer/MQTT/camera hardware đang hoạt động.
4. Nếu cần bốn đồ thị cảm biến nhưng mock hiện tại chưa cung cấp đủ, dùng video/đồ họa mô phỏng đã ghi rõ nguồn. Không sửa raw đo thật hoặc chèn sample giả vào phiên MEASURED.
5. Phần 35–60 giây nói: “Tín hiệu mô phỏng giúp kiểm thử hiển thị. Đây là sơ đồ ghép timestamp; nghiệm thu đồng bộ dùng phép đo trên thiết bị thật.” Không hiện PASS kỹ thuật từ tín hiệu mô phỏng.
6. Phần 60–95 giây dùng kết quả webcam/DEMO thật do pipeline tạo, với nhãn “DEMO / draft”; vẫn chỉ nhận nhãn và đối chiếu có trong dữ liệu.
7. Phần 95–120 giây dùng gói mô phỏng có provenance hoặc mở mẫu cấu trúc được ghi rõ “schema minh họa”. Không gọi đó là dataset robot-ready hoặc bằng chứng cải thiện đào tạo.

### C. Rút xuống 90 giây

Giữ cấu trúc: 0–18 giây vấn đề/thiết bị; 18–45 giây FPV–ADC–ghép; 45–72 giây segmentation–DTW–SOP; 72–90 giây gói quan sát và pilot. Bỏ cảnh macro/BOM và rút cảnh đồ thị, giữ nguyên nhãn nguồn và các giới hạn số liệu. Không nói nhanh hơn để nhồi đủ lời của bản 120 giây.

## Tài liệu nguồn trong dự án

- [Hướng dẫn chạy dự án](HUONG_DAN_CHAY_DU_AN.md)
- [Cải tiến và hiệu suất 09/10](IMPROVEMENTS_20261009.md)
- [Kiểm chứng phần cứng 07/10](layer1-layer3/VERIFICATION-20261007.md)
- [Read-back gói dữ liệu](DATA_PRODUCTS_REVIEW_20261007.md)
- [Hợp đồng dữ liệu và ngưỡng ghép](layer1-layer3/CONTRACT.md)
- [Hai workflow demo](DEMO_TWO_WORKFLOWS.md)
- [Thí nghiệm học việc](demo-kit/LEARNING_EXPERIMENT.md)
