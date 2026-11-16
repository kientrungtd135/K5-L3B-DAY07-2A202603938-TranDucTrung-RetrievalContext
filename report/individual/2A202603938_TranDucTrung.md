# Báo cáo Day 7

**Họ tên:** Trần Đức Trung — **MSSV:** 2A202603938 — **Lớp:** L3B.

## Dữ liệu và benchmark

- Nguồn, quyền sử dụng, số trang và số chunk: kế thừa corpus Day 6 gồm 30 bài Markdown và 701 chunk B. page=1 là đơn vị bài viết, không phải trang PDF. Nguồn MultiHopRAG khai báo ODC-BY; quyền riêng từng bài báo chưa được xác nhận. URL/attribution được giữ trong manifest nguồn và trace.
- Vector store, embedding model, phiên bản và số chiều: PostgreSQL 16 + pgvector 0.8.7; public.day6_chunks, strategy B, cosine exact; text-embedding-3-small, 1536 chiều. Phiên bản Python/package và nguồn tái tạo được ghi trong chi tiết bên dưới và README.
- Agent model, cách chạy và phân chia dev/test: deepseek-v4.1-flash; dev 15 câu có đáp án + 2 câu thiếu evidence; test 5 câu có đáp án + 2 câu thiếu evidence. Chọn trên dev, chốt cấu hình trước test; lệnh tại [hướng dẫn chạy](#submission-run-guide).
- Cách xác định câu có/thiếu evidence và tiêu chí chấm: gold có source, page và evidence; câu thiếu evidence có lý do và dấu vết kiểm tra corpus trong benchmark/absence_audit.json. Grounded/context chấm 0/1/2; citation cần thuộc context và hỗ trợ nội dung. Trạng thái nhãn hiện có: ai_proposed; giữ nguyên nhãn đã lưu, không tự chuyển thành human_confirmed.

<details>
<summary>Chi tiết dữ liệu, quyền sử dụng và benchmark</summary>

Kế thừa index B Day 6: 30 bài Markdown, gồm 15 business và 15 technology; chunk theo đoạn với max_size=500 ký tự, tổng cộng 701 chunk. page=1 là đơn vị bài viết, không phải trang PDF.



Vector store: PostgreSQL 16 + pgvector 0.8.7, bảng public.day6_chunks, strategy B, tìm kiếm cosine exact. Embedding: text-embedding-3-small, 1536 chiều. Agent thật: deepseek-v4.1-flash qua API tương thích OpenAI tại https://api.xah.io/v1. Model ID là alias provider, không bảo đảm snapshot bất biến.



Môi trường đã chạy: Windows, Python 3.13.3; openai 2.54.0, psycopg 3.3.8, python-dotenv 1.2.4, rank-bm25 0.2.2, numpy 2.5.5, pypdf 6.21.4. Các dependency được pin trong requirements.txt.



Benchmark gồm 24 câu: dev có 15 câu có đáp án + 2 câu thiếu evidence; test có 5 câu có đáp án mới + 2 câu thiếu evidence. Dev tái sử dụng câu hỏi dev Day 6. Năm câu test có đáp án dùng nguồn khác các nguồn câu hỏi Day 6. Cả 20 gold quote đều nằm trọn trong chunk B đúng source/page. Agent chỉ nhận câu hỏi và filter được cung cấp, không nhận expected answer, gold hoặc absence reason.



Bốn câu thiếu evidence hỏi về tỷ trọng doanh số Ripple Rug năm 2022, lợi nhuận sau thuế Betashares FY2023, giá thuê bao Mozilla.social và phán quyết bồi thường Helena World Chronicle. Lý do và dấu vết tìm kiếm nằm trong benchmark/absence_audit.json. AI đối chiếu nguồn liên quan và tìm trong corpus; không kết luận thiếu dữ liệu chỉ từ top-k. Nhãn absence chưa có xác nhận độc lập.



Nguồn dữ liệu là subset MultiHopRAG, dataset khai báo ODC-BY. URL/attribution được giữ trong manifest và trace. License dataset không xác nhận riêng quyền phân phối từng bài báo. Day 7 cung cấp nguồn Day 6 và cách tái tạo; trace vẫn chứa các đoạn nguồn đã dùng.



Nguồn Day 6: Manifest tại starter/data/manifest.json trong repo.

</details>

## Retrieval và thử nghiệm

Bảng dưới đánh giá pipeline agent: Hit@1/Hit@3 dùng query model viết lại ở lượt search đầu; Context Evidence Rate dùng context cuối đã chấm. Kết quả query gốc của cả ba phương pháp được báo riêng ngay bên dưới, không trộn hai loại query.

| Cấu hình | Phương pháp, top-k, filter, rerank, context budget | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | Context Evidence Rate | Thời gian / chi phí |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline — dense_baseline | dense; top-k=3; filter=theo câu hỏi; reranker model=không; budget=4000 ký tự; search tối đa=1 | Baseline dense trên vector store Day 6. | dev | 12/15 (80.0%) | 14/15 (93.3%) | 14/15 (93.3%) | median=5813.39 ms; model cost raw=109.68; embedding cost raw=102.00 |
| Phương pháp 2 — bm25_candidate | bm25; top-k=3; filter=theo câu hỏi; reranker model=không; budget=4000 ký tự; search tối đa=1 | Khớp từ khóa/tên riêng, giảm chi phí embedding. | dev | 15/15 (100.0%) | 15/15 (100.0%) | 15/15 (100.0%) | median=4331.58 ms; model cost raw=115.66; embedding cost raw=N/A |
| Phương pháp 3 — hybrid_candidate | hybrid; top-k=3; filter=theo câu hỏi; reranker model=không; budget=4000 ký tự; search tối đa=1; RRF=60, candidate=10/nhánh | RRF kết hợp lexical và semantic evidence. | dev | 15/15 (100.0%) | 15/15 (100.0%) | 15/15 (100.0%) | median=5688.32 ms; model cost raw=123.74; embedding cost raw=102.00 |
| Cải thiện 1 — auto_candidate | auto; top-k=3; filter=theo câu hỏi; reranker model=không; budget=4000 ký tự; search tối đa=3; RRF=60, candidate=10/nhánh | Chọn tool, viết lại query và tìm bổ sung. | dev | 13/15 (86.7%) | 15/15 (100.0%) | 15/15 (100.0%) | median=7147.41 ms; model cost raw=135.20; embedding cost raw=162.00 |
| Cải thiện 2 — auto_english_v2 | auto; top-k=3; filter=theo câu hỏi; reranker model=không; budget=4000 ký tự; search tối đa=3; RRF=60, candidate=10/nhánh | Auto + prompt ngắn, guard ngôn ngữ/citation abstention. | dev | 15/15 (100.0%) | 15/15 (100.0%) | 15/15 (100.0%) | median=9047.94 ms; model cost raw=142.39; embedding cost raw=156.00 |
| Cấu hình đã chọn — auto_english_v2 | auto; top-k=3; filter=không; reranker model=không; budget=4000 ký tự; search tối đa=3; RRF=60, candidate=10/nhánh | Auto + prompt ngắn, guard ngôn ngữ/citation abstention. | test | 2/5 (40.0%) | 5/5 (100.0%) | 5/5 (100.0%) | median=9535.72 ms; model cost raw=67.08; embedding cost raw=60.00 |
| Baseline — dense_baseline | dense; top-k=3; filter=không; reranker model=không; budget=4000 ký tự; search tối đa=1 | Baseline dense trên vector store Day 6. | test | 3/5 (60.0%) | 4/5 (80.0%) | 4/5 (80.0%) | median=5029.86 ms; model cost raw=43.32; embedding cost raw=42.00 |

BM25 và hybrid đồng thời là phương pháp mới và cấu hình thử cải thiện. Auto và v2 là các thử nghiệm tiếp theo. Chi phí raw chưa xác nhận đơn vị tiền tệ, không quy đổi USD; N/A embedding ở BM25 nghĩa là không gọi embedding.

<details>
<summary>Thiết lập và giả thuyết từng cấu hình</summary>

| Profile | Thay đổi / giả thuyết | Search tối đa |

| --- | --- | --- |

| dense_baseline | Dense exact cosine trên vector Day 6 | 1 |

| bm25_candidate | Khớp tên riêng/từ khóa, giảm độ trễ | 1 |

| hybrid_candidate | Kết hợp lexical và semantic để bổ sung evidence | 1 |

| auto_candidate | Model chọn tool và viết lại query, tìm bổ sung | 3 |

| auto_english_v2 | Auto + prompt ngắn, guard CJK/citation abstention | 3 |



Mọi profile: top-k=3, context budget=4000 ký tự gồm ID/URL/vị trí/text, temperature=0, max output=1024 token. Chỉ dùng category filter do câu hỏi cung cấp, không suy ra từ gold. BM25 dùng NFC/casefold, regex \w+, k1=1.5, b=0.75. Hybrid lấy tối đa 10 candidate mỗi nhánh rồi RRF với hằng số 60; không cộng trực tiếp hai loại score. Không dùng reranker.



Agent có search_dense, search_bm25, search_hybrid và finish_answer; profile đơn phương pháp chỉ có search tool tương ứng. Context tích lũy ưu tiên kết quả mới, khử trùng ID và giữ nguyên chunk vừa budget. Tool output cũ được thay bằng thông báo dùng context mới nhất. Khi hết lượt search, buộc finish; model turn tối đa bằng max_searches+4. Lỗi API/database được ghi thành error, không thay bằng abstain giả.



Validator kiểm tra citation thuộc context và khớp inline/list. V2 thêm chặn CJK và cấm citation cả inline lẫn list khi abstain. Guard không tự chứng minh semantic support và không phải bộ nhận diện đầy đủ mọi ngôn ngữ.

</details>

**Kết quả với query gốc:**

Hit@1/Hit@3 đếm câu có gold evidence đúng source/page trong top-1/top-3, chia số câu có đáp án. Exact context match kiểm tra gold còn trong context sau packing. Đây là query gốc, tách khỏi query model viết lại.



Dev latency tính trên 17 query thành công; test trên 5 câu có đáp án. Câu thiếu evidence không nằm trong mẫu số hit/context.



| Split | Method | Hit@1 | Hit@3 | Context match | Median ms | Errors |

| --- | --- | --- | --- | --- | --- | --- |

| dev | dense | 14/15 (93.3%) | 15/15 (100.0%) | 15/15 (100.0%) | 1,575.71 | 0 |

| dev | bm25 | 15/15 (100.0%) | 15/15 (100.0%) | 15/15 (100.0%) | 3.06 | 0 |

| dev | hybrid | 15/15 (100.0%) | 15/15 (100.0%) | 15/15 (100.0%) | 1,547.14 | 0 |

| test | dense | 5/5 (100.0%) | 5/5 (100.0%) | 5/5 (100.0%) | 1,353.78 | 0 |

| test | bm25 | 4/5 (80.0%) | 4/5 (80.0%) | 4/5 (80.0%) | 8.24 | 0 |

| test | hybrid | 4/5 (80.0%) | 4/5 (80.0%) | 4/5 (80.0%) | 1,428.99 | 0 |

**Hai lỗi dev, nguyên nhân, cách thử và lý do chọn cấu hình:**

1. **d7-dev-q09 — từ chối nhầm.** Query gốc dense có evidence newsletter tại rank 2, nhưng query baseline do model viết lại lấy các đoạn podcast ở doc_0012, thiếu lịch newsletter ở doc_0010. Một search không khôi phục được evidence: grounded/context 0. Auto bổ sung search; v2 trả lời đúng Thursday 12 p.m. PT, grounded/context 2. Query gốc tốt không bảo đảm query viết lại tốt.



2. **d7-dev-q13 — thêm chi tiết thiếu evidence.** Dense/BM25/hybrid trả lời đúng phần API nhưng hoàn tất thêm ý wireless-carrier từ câu bị cắt mà chưa có continuation trong context. Chấm bảo thủ grounded 1, citation chưa hỗ trợ toàn bộ câu. Auto v1 có các đoạn bổ sung nên được 2; v2 chỉ trả lời phần hỏi và được 2. Exact gold match không có nghĩa toàn bộ câu đều được hỗ trợ.



3. **Ngôn ngữ và citation khi abstain.** V1 có 2/4/2 lỗi ngôn ngữ ở dense/BM25/hybrid. Hybrid dev-u02 có inline citation nhưng list rỗng: citation hỗ trợ nguồn vẫn tính vào denominator, đồng thời báo một lỗi format. V2 thêm guard/prompt và sáu regression tests. Hai repair v2 dev là sửa citation ở q03/q07, không phải sửa ngôn ngữ.



BM25 và hybrid là hai cấu hình thử cải thiện, đồng thời là hai phương pháp retrieval mới. Auto và v2 là các thử nghiệm tiếp theo. Tiêu chí ban đầu: mean grounded cao nhất, rồi context, citation, latency. Trong dev, chính sách được điều chỉnh ưu tiên implementation có guard ngôn ngữ/citation abstention; thay đổi và lý do được ghi trong final_selection trước test.



Auto v1 cũng đạt 30/30 điểm dev và nhanh hơn v2. Nếu chỉ dùng tiêu chí điểm và latency ban đầu, Auto v1 sẽ được ưu tiên. V2 được chọn vì guard ở mức code cùng prompt hạn chế phát biểu thêm, chấp nhận latency cao hơn; không tuyên bố v2 tăng factual accuracy dev so với Auto v1. Guard v1 vẫn có lỗ hổng dù các output Auto v1 quan sát được đều đạt.



Test chỉ chạy sau freeze; không sửa prompt/parameter theo lỗi test hoặc chạy lại câu thành công để chọn kết quả đẹp. Test-02 baseline từ chối nhầm vì query viết lại không tìm được counts, còn v2 tìm đủ evidence. Test-03 v2 cần 6 model calls, 2 searches và 2 citation repairs; giữ nguyên trong trace.



Dense query gốc test đạt 5/5, BM25/hybrid đạt 4/5; không kết luận hybrid luôn tốt hơn dense.

## Agent và đánh giá

- Tool, số lượt gọi, điều kiện dừng, cách chọn context và xử lý lỗi: search_dense/search_bm25/search_hybrid và finish_answer; profile đơn phương pháp chỉ có search tương ứng. Context ưu tiên kết quả mới, khử trùng ID, giữ nguyên chunk vừa budget 4000 ký tự. Hết lượt search thì buộc finish; model turn tối đa=max_searches+4. Lỗi API/database ghi thành error, không đổi thành abstain giả. Validator kiểm tra ID và format citation; semantic support dựa trên nhãn đối chiếu evidence.

| Cấu hình / split | Tool use | Số lượt gọi | Grounded answer 0/1/2 và trung bình | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dense_baseline / dev | 17/17 (100.0%) | model=34; search=17; embedding=17 | mức 0/1/2: 1/1/13; mean=1.800/2 | 16/17 (94.1%) | 14/14 (100.0%) | 2/2 (100.0%) | 1/15 (6.7%) |
| bm25_candidate / dev | 17/17 (100.0%) | model=34; search=17; embedding=0 | mức 0/1/2: 0/1/14; mean=1.933/2 | 18/19 (94.7%) | 15/15 (100.0%) | 2/2 (100.0%) | 0/15 (0.0%) |
| hybrid_candidate / dev | 17/17 (100.0%) | model=34; search=17; embedding=17 | mức 0/1/2: 0/1/14; mean=1.933/2 | 17/18 (94.4%) | 15/15 (100.0%) | 2/2 (100.0%) | 0/15 (0.0%) |
| auto_candidate / dev | 17/17 (100.0%) | model=40; search=36; embedding=27 | mức 0/1/2: 0/0/15; mean=2.000/2 | 19/19 (100.0%) | 15/15 (100.0%) | 2/2 (100.0%) | 0/15 (0.0%) |
| auto_english_v2 / dev | 17/17 (100.0%) | model=41; search=36; embedding=26 | mức 0/1/2: 0/0/15; mean=2.000/2 | 18/18 (100.0%) | 15/15 (100.0%) | 2/2 (100.0%) | 0/15 (0.0%) |
| auto_english_v2 / test | 7/7 (100.0%) | model=20; search=16; embedding=10 | mức 0/1/2: 0/0/5; mean=2.000/2 | 5/5 (100.0%) | 5/5 (100.0%) | 2/2 (100.0%) | 0/5 (0.0%) |
| dense_baseline / test | 7/7 (100.0%) | model=14; search=7; embedding=7 | mức 0/1/2: 1/0/4; mean=1.600/2 | 5/5 (100.0%) | 4/4 (100.0%) | 2/2 (100.0%) | 1/5 (20.0%) |

<details>
<summary>Chi tiết context, ranking và đánh giá agent</summary>

Grounded: 0=sai/thiếu evidence hoặc từ chối nhầm; 1=đúng một phần; 2=đúng và đủ. Context: 0=không có evidence; 1=thiếu điều kiện/nguồn; 2=đủ. Context Evidence Rate là số câu context mức 2 / số câu có đáp án.



Citation phải thuộc context và hỗ trợ câu trả lời; đếm ID duy nhất mỗi câu, gồm cả inline ID không có trong list. Lỗi ngôn ngữ báo riêng với factual grade.



| Split | Profile | Số mức 0/1/2 | Mean | Context đủ | Citation hợp lệ | Abstention đúng | Từ chối nhầm |

| --- | --- | --- | --- | --- | --- | --- | --- |

| dev | dense_baseline | 1/1/13 | 1.800/2 | 14/15 (93.3%) | 16/17 (94.1%) | 2/2 (100.0%) | 1/15 (6.7%) |

| dev | bm25_candidate | 0/1/14 | 1.933/2 | 15/15 (100.0%) | 18/19 (94.7%) | 2/2 (100.0%) | 0/15 (0.0%) |

| dev | hybrid_candidate | 0/1/14 | 1.933/2 | 15/15 (100.0%) | 17/18 (94.4%) | 2/2 (100.0%) | 0/15 (0.0%) |

| dev | auto_candidate | 0/0/15 | 2.000/2 | 15/15 (100.0%) | 19/19 (100.0%) | 2/2 (100.0%) | 0/15 (0.0%) |

| dev | auto_english_v2 | 0/0/15 | 2.000/2 | 15/15 (100.0%) | 18/18 (100.0%) | 2/2 (100.0%) | 0/15 (0.0%) |

| test | dense_baseline | 1/0/4 | 1.600/2 | 4/5 (80.0%) | 5/5 (100.0%) | 2/2 (100.0%) | 1/5 (20.0%) |

| test | auto_english_v2 | 0/0/5 | 2.000/2 | 5/5 (100.0%) | 5/5 (100.0%) | 2/2 (100.0%) | 0/5 (0.0%) |



| Split | Profile | Tool use | Câu có citation | Lỗi ngôn ngữ | Lỗi inline/list | Median ms | Errors |

| --- | --- | --- | --- | --- | --- | --- | --- |

| dev | dense_baseline | 17/17 (100.0%) | 14/14 (100.0%) | 2 | 0 | 5,813.39 | 0 |

| dev | bm25_candidate | 17/17 (100.0%) | 15/15 (100.0%) | 4 | 0 | 4,331.58 | 0 |

| dev | hybrid_candidate | 17/17 (100.0%) | 15/15 (100.0%) | 2 | 1 | 5,688.32 | 0 |

| dev | auto_candidate | 17/17 (100.0%) | 15/15 (100.0%) | 0 | 0 | 7,147.41 | 0 |

| dev | auto_english_v2 | 17/17 (100.0%) | 15/15 (100.0%) | 0 | 0 | 9,047.94 | 0 |

| test | dense_baseline | 7/7 (100.0%) | 4/4 (100.0%) | 0 | 0 | 5,029.86 | 0 |

| test | auto_english_v2 | 7/7 (100.0%) | 5/5 (100.0%) | 0 | 0 | 9,535.72 | 0 |



Ranking lượt search đầu với query model viết lại (khác bảng query gốc):



| Split | Profile | First Hit@1 | First Hit@3 |

| --- | --- | --- | --- |

| dev | dense_baseline | 12/15 (80.0%) | 14/15 (93.3%) |

| dev | bm25_candidate | 15/15 (100.0%) | 15/15 (100.0%) |

| dev | hybrid_candidate | 15/15 (100.0%) | 15/15 (100.0%) |

| dev | auto_candidate | 13/15 (86.7%) | 15/15 (100.0%) |

| dev | auto_english_v2 | 15/15 (100.0%) | 15/15 (100.0%) |

| test | dense_baseline | 3/5 (60.0%) | 4/5 (80.0%) |

| test | auto_english_v2 | 2/5 (40.0%) | 5/5 (100.0%) |

</details>

<a id="kiem-chung-test"></a>

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
| --- | --- | --- | --- | --- |
| d7-test-01 / dense_baseline | Có evidence: According to the Google Search article, approximately how many zettabytes of data were people creating every year in 2013? | search_dense(Google Search article zettabytes of data created every year 2013) → doc_0033/page 1, doc_0033/page 1, doc_0033/page 1<br>[Trace đầy đủ](../../results/agent_test_final/dense_baseline/d7-test-01.json) | In 2013, people were creating around 9 zettabytes (ZB) of data every year, compared with roughly 120 ZB in 2023 [by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211][by_paragraph-d6297f29eea6dfe95baf83dc7d00f2e091cc0f7e101e96886188d33c74e5dc38].<br>Citation list: ["by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211", "by_paragraph-d6297f29eea6dfe95baf83dc7d00f2e091cc0f7e101e96886188d33c74e5dc38"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: Around 9 zettabytes (9 ZB) per year. Both cited chunks jointly support the added 2023 comparison. |
| d7-test-01 / auto_english_v2 | Có evidence: According to the Google Search article, approximately how many zettabytes of data were people creating every year in 2013? | search_bm25(Google Search article zettabytes data created every year 2013) → doc_0033/page 1, doc_0033/page 1, doc_0034/page 1<br>search_dense(how many zettabytes of data people creating every year 2013) → doc_0033/page 1, doc_0033/page 1, doc_0012/page 1<br>[Trace đầy đủ](../../results/agent_test_final/auto_english_v2/d7-test-01.json) | In 2013, people were creating around 9 zettabytes (ZB) of data every year, according to the article. [by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211]<br>Citation list: ["by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: Around 9 zettabytes (9 ZB) per year. |
| d7-test-02 / dense_baseline | Có evidence: According to the Helena World Chronicle lawsuit article, how many facts and entities did Google's Knowledge Graph contain by 2020? | search_dense(Helena World Chronicle lawsuit Google Knowledge Graph facts entities 2020) → doc_0034/page 1, doc_0034/page 1, doc_0034/page 1<br>[Trace đầy đủ](../../results/agent_test_final/dense_baseline/d7-test-02.json) | The corpus does not provide enough evidence: the Helena World Chronicle lawsuit article mentions the Knowledge Graph (launched May 2012) but does not state how many facts and entities it contained by 2020.<br>Citation list: [] | grounded=0; context=0; abstention_correct=None; review_status=ai_proposed. False abstention. Retrieved context lacks the requested counts, but doc_0034 in the corpus states 500 billion facts about 5 billion entities by 2020. |
| d7-test-02 / auto_english_v2 | Có evidence: According to the Helena World Chronicle lawsuit article, how many facts and entities did Google's Knowledge Graph contain by 2020? | search_hybrid(Helena World Chronicle lawsuit Google Knowledge Graph facts entities 2020) → doc_0034/page 1, doc_0034/page 1, doc_0034/page 1<br>search_bm25(Knowledge Graph 500 billion facts 5 billion entities) → doc_0034/page 1, doc_0011/page 1, doc_0034/page 1<br>[Trace đầy đủ](../../results/agent_test_final/auto_english_v2/d7-test-02.json) | By 2020, Google's Knowledge Graph had grown to 500 billion facts about 5 billion entities, according to the lawsuit article. [by_paragraph-12c20f27e1251d18c440423d14c8faca25919a3d2b5e8c1a2e2789a760062df8]<br>Citation list: ["by_paragraph-12c20f27e1251d18c440423d14c8faca25919a3d2b5e8c1a2e2789a760062df8"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: 500 billion facts about 5 billion entities. |
| d7-test-03 / dense_baseline | Có evidence: According to the Epic Games trial preview, what commission range did Google charge app developers on sales processed through its first-party billing system? | search_dense(Epic Games trial preview Google commission range app developers first-party billing system) → doc_0043/page 1, doc_0043/page 1, doc_0043/page 1<br>[Trace đầy đủ](../../results/agent_test_final/dense_baseline/d7-test-03.json) | According to the trial preview, Google requires apps to use its first-party billing system and charges app developers a 15% to 30% commission on the sales it processes [by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a].<br>Citation list: ["by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: 15% to 30%. |
| d7-test-03 / auto_english_v2 | Có evidence: According to the Epic Games trial preview, what commission range did Google charge app developers on sales processed through its first-party billing system? | search_hybrid(Epic Games trial preview Google commission range app developers first-party billing system) → doc_0043/page 1, doc_0043/page 1, doc_0043/page 1<br>search_hybrid(Google requires apps first-party billing system charges app developers 15% to 30% commission sales it processes) → doc_0043/page 1, doc_0043/page 1, doc_0043/page 1<br>[Trace đầy đủ](../../results/agent_test_final/auto_english_v2/d7-test-03.json) | Google charged app developers a 15% to 30% commission on sales processed through its first-party billing system [by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a].<br>Citation list: ["by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: 15% to 30%. Final answer is supported after two logged citation repairs. |
| d7-test-04 / dense_baseline | Có evidence: In the Manchester United article, what planned infrastructure investment amount is mentioned in US dollars and pounds? | search_dense(Manchester United planned infrastructure investment dollars pounds) → doc_0090/page 1, doc_0090/page 1, doc_0090/page 1<br>[Trace đầy đủ](../../results/agent_test_final/dense_baseline/d7-test-04.json) | The article mentions a planned investment of $300m (£237m) into infrastructure [by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e].<br>Citation list: ["by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: US$300 million, equivalent to 237 million pounds. |
| d7-test-04 / auto_english_v2 | Có evidence: In the Manchester United article, what planned infrastructure investment amount is mentioned in US dollars and pounds? | search_hybrid(Manchester United planned infrastructure investment US dollars pounds) → doc_0090/page 1, doc_0090/page 1, doc_0090/page 1<br>search_bm25(Manchester United infrastructure investment £ $ billion) → doc_0090/page 1, doc_0090/page 1, doc_0090/page 1<br>[Trace đầy đủ](../../results/agent_test_final/auto_english_v2/d7-test-04.json) | The article mentions a planned infrastructure investment of $300m (£237m). [by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e]<br>Citation list: ["by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: US$300 million, equivalent to 237 million pounds. |
| d7-test-05 / dense_baseline | Có evidence: According to the Menendez article, what was the reported dollar value of gold bars found in the raid on his house? | search_dense(Menendez article dollar value gold bars found in raid on his house) → doc_0098/page 1, doc_0028/page 1, doc_0032/page 1<br>[Trace đầy đủ](../../results/agent_test_final/dense_baseline/d7-test-05.json) | The article reported that the raid on Menendez’s house turned up **$100,000 in gold bars** [by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639].<br>Citation list: ["by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: $100,000. |
| d7-test-05 / auto_english_v2 | Có evidence: According to the Menendez article, what was the reported dollar value of gold bars found in the raid on his house? | search_hybrid(Menendez gold bars found in raid on his house dollar value) → doc_0098/page 1, doc_0028/page 1, doc_0074/page 1<br>search_bm25(Menendez gold bars raid house value) → doc_0098/page 1, doc_0074/page 1, doc_0031/page 1<br>[Trace đầy đủ](../../results/agent_test_final/auto_english_v2/d7-test-05.json) | The article reports that the raid on Menendez's house turned up $100,000 in gold bars, along with bundles of cash stuffed into jacket pockets [by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639].<br>Citation list: ["by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639"] | grounded=2; context=2; abstention_correct=None; review_status=ai_proposed. Answer and cited evidence were inspected in the supplied test packet. Required fact: $100,000. |
| d7-test-u01 / dense_baseline | Thiếu evidence: What exact monthly subscription price in US dollars did Mozilla announce for Mozilla.social? | search_dense(Mozilla.social monthly subscription price US dollars) → doc_0016/page 1, doc_0027/page 1, doc_0027/page 1<br>[Trace đầy đủ](../../results/agent_test_final/dense_baseline/d7-test-u01.json) | The corpus does not provide enough evidence: the retrieved articles on Mozilla.social discuss Mozilla accounts and the instance's testing phase, but no monthly subscription price in US dollars is reported.<br>Citation list: [] | grounded=None; context=None; abstention_correct=True; review_status=ai_proposed. Correct abstention for this corpus benchmark. The article describes a private beta and moderation plans but gives no monthly subscription price. Absence of a price does not imply a zero-dollar price. |
| d7-test-u01 / auto_english_v2 | Thiếu evidence: What exact monthly subscription price in US dollars did Mozilla announce for Mozilla.social? | search_hybrid(Mozilla.social monthly subscription price US dollars announced) → doc_0027/page 1, doc_0027/page 1, doc_0027/page 1<br>search_bm25(Mozilla.social subscription price per month) → doc_0027/page 1, doc_0027/page 1, doc_0027/page 1<br>search_dense(Mozilla.social paid subscription cost per month dollars) → doc_0016/page 1, doc_0027/page 1, doc_0027/page 1<br>[Trace đầy đủ](../../results/agent_test_final/auto_english_v2/d7-test-u01.json) | The corpus does not provide enough evidence to confirm the exact monthly subscription price Mozilla announced for Mozilla.social.<br>Citation list: [] | grounded=None; context=None; abstention_correct=True; review_status=ai_proposed. Correct abstention for this corpus benchmark. The article describes a private beta and moderation plans but gives no monthly subscription price. Absence of a price does not imply a zero-dollar price. |
| d7-test-u02 / dense_baseline | Thiếu evidence: What exact dollar amount in damages did the court ultimately award Helena World Chronicle in its lawsuit against Google? | search_dense(Helena World Chronicle lawsuit against Google damages awarded) → doc_0034/page 1, doc_0034/page 1, doc_0034/page 1<br>[Trace đầy đủ](../../results/agent_test_final/dense_baseline/d7-test-u02.json) | The corpus does not provide enough evidence to answer this. The only relevant material describes the December 2023 class action filed by Helena World Chronicle against Google and Alphabet, but it reports no damages award or outcome, so no dollar amount can be given.<br>Citation list: [] | grounded=None; context=None; abstention_correct=True; review_status=ai_proposed. Correct abstention for this corpus benchmark. The snapshot describes a newly filed lawsuit and requested relief, not a damages award. Google's Canadian media agreement is a different matter. |
| d7-test-u02 / auto_english_v2 | Thiếu evidence: What exact dollar amount in damages did the court ultimately award Helena World Chronicle in its lawsuit against Google? | search_hybrid(Helena World Chronicle lawsuit against Google damages awarded) → doc_0034/page 1, doc_0034/page 1, doc_0034/page 1<br>search_bm25(Helena World Chronicle Google) → doc_0034/page 1, doc_0034/page 1, doc_0034/page 1<br>search_dense(Helena World Chronicle verdict damages awarded amount outcome ruling) → doc_0034/page 1, doc_0003/page 1, doc_0034/page 1<br>[Trace đầy đủ](../../results/agent_test_final/auto_english_v2/d7-test-u02.json) | The corpus does not provide enough evidence to state a damages award in this case.<br>Citation list: [] | grounded=None; context=None; abstention_correct=True; review_status=ai_proposed. Correct abstention for this corpus benchmark. The snapshot describes a newly filed lawsuit and requested relief, not a damages award. Google's Canadian media agreement is a different matter. |

- Đường dẫn trace, nhãn, lệnh chạy, thời gian và chi phí: results/agent_dev_v1/, results/agent_dev_v2/, results/agent_test_final/; nhãn ở reviews.json mỗi run; ranking query gốc dev ở results/retrieval_dev/, test ở results/agent_test_final/raw_retrieval/. Tổng hợp ở results/submission_summary.json; lệnh tại [hướng dẫn chạy](#submission-run-guide).

<details>
<summary>Lượt gọi, phân bố, token và chi phí đã lưu</summary>

Đơn vị thời gian ms. Median agent tính trên toàn bộ 17 dev hoặc 7 test thành công, không gồm khởi tạo retriever và ghi file; có độ trễ API/network. Model call là SDK call, không thấy retry HTTP nội bộ.



Bảng gồm cả câu thiếu evidence. Token/chi phí lấy từ usage đã lưu. Chi phí là x_ckey.cost thô do provider trả về, chưa xác minh đơn vị hoặc đối soát hóa đơn; không quy đổi USD. BM25 không gọi embedding nên ghi 0 lượt, token/phí embedding N/A.



| Split | Profile | Model calls | Search calls | Embed calls | Model tokens | Embed tokens | Model cost raw | Embed cost raw |

| --- | --- | --- | --- | --- | --- | --- | --- | --- |

| dev | dense_baseline | 34 | 17 | 17 | 33469 | 219 | 109.68 | 102.00 |

| dev | bm25_candidate | 34 | 17 | 0 | 33897 | N/A | 115.66 | N/A |

| dev | hybrid_candidate | 34 | 17 | 17 | 33773 | 212 | 123.74 | 102.00 |

| dev | auto_candidate | 40 | 36 | 27 | 55748 | 343 | 135.20 | 162.00 |

| dev | auto_english_v2 | 41 | 36 | 26 | 63502 | 329 | 142.39 | 156.00 |

| test | dense_baseline | 14 | 7 | 7 | 13425 | 77 | 43.32 | 42.00 |

| test | auto_english_v2 | 20 | 16 | 10 | 32040 | 117 | 67.08 | 60.00 |



Phân bố dạng số_lượt:số_câu. Non-tool turn là response không có tool call, phân biệt với citation repair:



| Split | Profile | Model calls | Search calls | Repairs | Non-tool turns |

| --- | --- | --- | --- | --- | --- |

| dev | dense_baseline | {"2": 17} | {"1": 17} | 0 | 0 |

| dev | bm25_candidate | {"2": 17} | {"1": 17} | 0 | 0 |

| dev | hybrid_candidate | {"2": 17} | {"1": 17} | 0 | 0 |

| dev | auto_candidate | {"2": 13, "4": 2, "3": 2} | {"2": 11, "1": 2, "3": 4} | 0 | 2 |

| dev | auto_english_v2 | {"2": 11, "3": 5, "4": 1} | {"2": 11, "1": 2, "3": 4} | 2 | 2 |

| test | dense_baseline | {"2": 7} | {"1": 7} | 0 | 0 |

| test | auto_english_v2 | {"2": 4, "6": 1, "3": 2} | {"2": 5, "3": 2} | 2 | 1 |



Chi phí query gốc tính riêng, không cộng lặp vào agent:



| Split/method | Embed calls | Embed tokens | Embed cost raw |

| --- | --- | --- | --- |

| dev_dense | 17 | 387 | 102.00 |

| test_dense | 5 | 119 | 30.00 |

| dev_bm25 | 0 | N/A | N/A |

| test_bm25 | 0 | N/A | N/A |

| dev_hybrid | 17 | 387 | 102.00 |

| test_hybrid | 5 | 119 | 30.00 |



Coverage usage/token/cost response xem [submission_summary.json](../../results/submission_summary.json). Tổng hợp không bao gồm smoke checks đã bỏ và phí tạo index Day 6; không phải tổng hóa đơn toàn buổi. Không có system error hay failed attempt trong các run được nộp.

</details>

<details>
<summary>Đối chiếu test trong báo cáo trước khi đổi form</summary>

Bảng lấy trực tiếp từ trace và reviews gốc. Các nhãn vẫn là **AI-proposed**, chưa được human-confirmed. Xem [phiếu kiểm chứng](#kiem-chung-test).



| Query ID / Profile | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |

|---|---|---|---|---|

| `d7-test-01` / `dense_baseline` | Answerable | `search_dense` (Google Search article zettabytes of data created every year 2013) -> doc_0033:p1, doc_0033:p1 | In 2013, people were creating around 9 zettabytes (ZB) of data every year, compared with roughly 120 ZB in 2023 .. Citations: `by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211`, `by_paragraph-d6297f29eea6dfe95baf83dc7d00f2e091cc0f7e101e96886188d33c74e5dc38`. [Trace](../../results/agent_test_final/dense_baseline/d7-test-01.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: Around 9 zettabytes (9 ZB) per year. Both cited chunks jointly support the added 2023 comparison. |

| `d7-test-01` / `auto_english_v2` | Answerable | `search_bm25` (Google Search article zettabytes data created every year 2013) -> doc_0033:p1, doc_0033:p1; `search_dense` (how many zettabytes of data people creating every year 2013) -> doc_0033:p1, doc_0033:p1 | In 2013, people were creating around 9 zettabytes (ZB) of data every year, according to the article.. Citations: `by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211`. [Trace](../../results/agent_test_final/auto_english_v2/d7-test-01.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: Around 9 zettabytes (9 ZB) per year. |

| `d7-test-02` / `dense_baseline` | Answerable | `search_dense` (Helena World Chronicle lawsuit Google Knowledge Graph facts entities 2020) -> doc_0034:p1, doc_0034:p1 | The corpus does not provide enough evidence: the Helena World Chronicle lawsuit article mentions the Knowledge Graph (launched May 2012) but does not state how many facts and entities it contained by 2020.. Citations: (none). [Trace](../../results/agent_test_final/dense_baseline/d7-test-02.json) | **G=0; C=0 (AI-proposed)**. False abstention. Retrieved context lacks the requested counts, but doc_0034 in the corpus states 500 billion facts about 5 billion entities by 2020. |

| `d7-test-02` / `auto_english_v2` | Answerable | `search_hybrid` (Helena World Chronicle lawsuit Google Knowledge Graph facts entities 2020) -> doc_0034:p1, doc_0034:p1; `search_bm25` (Knowledge Graph 500 billion facts 5 billion entities) -> doc_0034:p1, doc_0011:p1 | By 2020, Google's Knowledge Graph had grown to 500 billion facts about 5 billion entities, according to the lawsuit article.. Citations: `by_paragraph-12c20f27e1251d18c440423d14c8faca25919a3d2b5e8c1a2e2789a760062df8`. [Trace](../../results/agent_test_final/auto_english_v2/d7-test-02.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: 500 billion facts about 5 billion entities. |

| `d7-test-03` / `dense_baseline` | Answerable | `search_dense` (Epic Games trial preview Google commission range app developers first-party) -> doc_0043:p1, doc_0043:p1 | According to the trial preview, Google requires apps to use its first-party billing system and charges app developers a 15% to 30% commission on the sales it processes .. Citations: `by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a`. [Trace](../../results/agent_test_final/dense_baseline/d7-test-03.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: 15% to 30%. |

| `d7-test-03` / `auto_english_v2` | Answerable | `search_hybrid` (Epic Games trial preview Google commission range app developers first-party) -> doc_0043:p1, doc_0043:p1; `search_hybrid` (Google requires apps first-party billing system charges app developers 15% ) -> doc_0043:p1, doc_0043:p1 | Google charged app developers a 15% to 30% commission on sales processed through its first-party billing system .. Citations: `by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a`. [Trace](../../results/agent_test_final/auto_english_v2/d7-test-03.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: 15% to 30%. Final answer is supported after two logged citation repairs. |

| `d7-test-04` / `dense_baseline` | Answerable | `search_dense` (Manchester United planned infrastructure investment dollars pounds) -> doc_0090:p1, doc_0090:p1 | The article mentions a planned investment of $300m (£237m) into infrastructure .. Citations: `by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e`. [Trace](../../results/agent_test_final/dense_baseline/d7-test-04.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: US$300 million, equivalent to 237 million pounds. |

| `d7-test-04` / `auto_english_v2` | Answerable | `search_hybrid` (Manchester United planned infrastructure investment US dollars pounds) -> doc_0090:p1, doc_0090:p1; `search_bm25` (Manchester United infrastructure investment £ $ billion) -> doc_0090:p1, doc_0090:p1 | The article mentions a planned infrastructure investment of $300m (£237m).. Citations: `by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e`. [Trace](../../results/agent_test_final/auto_english_v2/d7-test-04.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: US$300 million, equivalent to 237 million pounds. |

| `d7-test-05` / `dense_baseline` | Answerable | `search_dense` (Menendez article dollar value gold bars found in raid on his house) -> doc_0098:p1, doc_0028:p1 | The article reported that the raid on Menendez’s house turned up **$100,000 in gold bars** .. Citations: `by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639`. [Trace](../../results/agent_test_final/dense_baseline/d7-test-05.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: $100,000. |

| `d7-test-05` / `auto_english_v2` | Answerable | `search_hybrid` (Menendez gold bars found in raid on his house dollar value) -> doc_0098:p1, doc_0028:p1; `search_bm25` (Menendez gold bars raid house value) -> doc_0098:p1, doc_0074:p1 | The article reports that the raid on Menendez's house turned up $100,000 in gold bars, along with bundles of cash stuffed into jacket pockets .. Citations: `by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639`. [Trace](../../results/agent_test_final/auto_english_v2/d7-test-05.json) | **G=2; C=2 (AI-proposed)**. Answer and cited evidence were inspected in the supplied test packet. Required fact: $100,000. |

| `d7-test-u01` / `dense_baseline` | Unanswerable | `search_dense` (Mozilla.social monthly subscription price US dollars) -> doc_0016:p1, doc_0027:p1 | The corpus does not provide enough evidence: the retrieved articles on Mozilla.social discuss Mozilla accounts and the instance's testing phase, but no monthly subscription price in US dollars is reported.. Citations: (none). [Trace](../../results/agent_test_final/dense_baseline/d7-test-u01.json) | **Abstention=correct (AI-proposed)**. Correct abstention for this corpus benchmark. The article describes a private beta and moderation plans but gives no monthly subscription price. Absence of a price does not imply a zero-dollar price. |

| `d7-test-u01` / `auto_english_v2` | Unanswerable | `search_hybrid` (Mozilla.social monthly subscription price US dollars announced) -> doc_0027:p1, doc_0027:p1; `search_bm25` (Mozilla.social subscription price per month) -> doc_0027:p1, doc_0027:p1; `search_dense` (Mozilla.social paid subscription cost per month dollars) -> doc_0016:p1, doc_0027:p1 | The corpus does not provide enough evidence to confirm the exact monthly subscription price Mozilla announced for Mozilla.social.. Citations: (none). [Trace](../../results/agent_test_final/auto_english_v2/d7-test-u01.json) | **Abstention=correct (AI-proposed)**. Correct abstention for this corpus benchmark. The article describes a private beta and moderation plans but gives no monthly subscription price. Absence of a price does not imply a zero-dollar price. |

| `d7-test-u02` / `dense_baseline` | Unanswerable | `search_dense` (Helena World Chronicle lawsuit against Google damages awarded) -> doc_0034:p1, doc_0034:p1 | The corpus does not provide enough evidence to answer this. The only relevant material describes the December 2023 class action filed by Helena World Chronicle against Google and Alphabet, but it reports no damages award or outcome, so no dollar amount can be given.. Citations: (none). [Trace](../../results/agent_test_final/dense_baseline/d7-test-u02.json) | **Abstention=correct (AI-proposed)**. Correct abstention for this corpus benchmark. The snapshot describes a newly filed lawsuit and requested relief, not a damages award. Google's Canadian media agreement is a different matter. |

| `d7-test-u02` / `auto_english_v2` | Unanswerable | `search_hybrid` (Helena World Chronicle lawsuit against Google damages awarded) -> doc_0034:p1, doc_0034:p1; `search_bm25` (Helena World Chronicle Google) -> doc_0034:p1, doc_0034:p1; `search_dense` (Helena World Chronicle verdict damages awarded amount outcome ruling) -> doc_0034:p1, doc_0003:p1 | The corpus does not provide enough evidence to state a damages award in this case.. Citations: (none). [Trace](../../results/agent_test_final/auto_english_v2/d7-test-u02.json) | **Abstention=correct (AI-proposed)**. Correct abstention for this corpus benchmark. The snapshot describes a newly filed lawsuit and requested relief, not a damages award. Google's Canadian media agreement is a different matter. |



G/C là groundedness/context theo thang 0-2. Unanswerable được chấm abstention riêng.



Các file trace và review gốc không thay đổi.

</details>

<details>
<summary>Phiếu kiểm chứng test và evidence đã gộp từ manual_review.md</summary>

### Day 7 - Phiếu kiểm chứng Test

**Trạng thái: CHƯA XÁC NHẬN THỦ CÔNG.**

Dữ liệu lấy từ trace và AI-proposed reviews.
Đọc evidence thực tế trước khi xác nhận nhãn.

Với câu thiếu evidence, kiểm tra thêm [absence_audit.json](../../benchmark/absence_audit.json).

### d7-test-01

**Question:** According to the Google Search article, approximately how many zettabytes of data were people creating every year in 2013?

**Expected:** Around 9 zettabytes (9 ZB) per year.

**Gold:** `doc_0033` / page 1 - In 2013, people were creating around 9 ZB of data every year

#### dense_baseline

[Full trace](../../results/agent_test_final/dense_baseline/d7-test-01.json)

**Tool calls:** `search_dense` (Google Search article zettabytes of data created every year 2013) -> doc_0033:p1, doc_0033:p1

**Final answer:** In 2013, people were creating around 9 zettabytes (ZB) of data every year, compared with roughly 120 ZB in 2023 [by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211][by_paragraph-d6297f29eea6dfe95baf83dc7d00f2e091cc0f7e101e96886188d33c74e5dc38].

**Citations:** `by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211`, `by_paragraph-d6297f29eea6dfe95baf83dc7d00f2e091cc0f7e101e96886188d33c74e5dc38`

**Cited evidence:**
- `by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211`: `doc_0033` / page 1: Similarly, it’s also pretty common to see people complaining on the internet with some variation of “Google Search was a lot better 10 years ago”, which could absolutely 
- `by_paragraph-d6297f29eea6dfe95baf83dc7d00f2e091cc0f7e101e96886188d33c74e5dc38`: `doc_0033` / page 1: ZB. And not a whole lot of that is static websites like it was a decade ago, it’s live information that may be nested within various services and apps. What really happen

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: Around 9 zettabytes (9 ZB) per year. Both cited chunks jointly support the added 2023 comparison.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

#### auto_english_v2

[Full trace](../../results/agent_test_final/auto_english_v2/d7-test-01.json)

**Tool calls:** `search_bm25` (Google Search article zettabytes data created every year 2013) -> doc_0033:p1, doc_0033:p1; `search_dense` (how many zettabytes of data people creating every year 2013) -> doc_0033:p1, doc_0033:p1

**Final answer:** In 2013, people were creating around 9 zettabytes (ZB) of data every year, according to the article. [by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211]

**Citations:** `by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211`

**Cited evidence:**
- `by_paragraph-d8e7f97a168ae7074647c17eaaea90b1c233730fc5580ea3d04ebbe1f0a12211`: `doc_0033` / page 1: Similarly, it’s also pretty common to see people complaining on the internet with some variation of “Google Search was a lot better 10 years ago”, which could absolutely 

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: Around 9 zettabytes (9 ZB) per year.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

### d7-test-02

**Question:** According to the Helena World Chronicle lawsuit article, how many facts and entities did Google's Knowledge Graph contain by 2020?

**Expected:** 500 billion facts about 5 billion entities.

**Gold:** `doc_0034` / page 1 - By 2020, the Knowledge Graph had grown to 500 billion facts about 5 billion entities.

#### dense_baseline

[Full trace](../../results/agent_test_final/dense_baseline/d7-test-02.json)

**Tool calls:** `search_dense` (Helena World Chronicle lawsuit Google Knowledge Graph facts entities 2020) -> doc_0034:p1, doc_0034:p1

**Final answer:** The corpus does not provide enough evidence: the Helena World Chronicle lawsuit article mentions the Knowledge Graph (launched May 2012) but does not state how many facts and entities it contained by 2020.

**Citations:** (none)

**Cited evidence:**
- No citations. Check abstention correctness.

**AI-proposed:** G=0; C=0. False abstention. Retrieved context lacks the requested counts, but doc_0034 in the corpus states 500 billion facts about 5 billion entities by 2020.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

#### auto_english_v2

[Full trace](../../results/agent_test_final/auto_english_v2/d7-test-02.json)

**Tool calls:** `search_hybrid` (Helena World Chronicle lawsuit Google Knowledge Graph facts entities 2020) -> doc_0034:p1, doc_0034:p1; `search_bm25` (Knowledge Graph 500 billion facts 5 billion entities) -> doc_0034:p1, doc_0011:p1

**Final answer:** By 2020, Google's Knowledge Graph had grown to 500 billion facts about 5 billion entities, according to the lawsuit article. [by_paragraph-12c20f27e1251d18c440423d14c8faca25919a3d2b5e8c1a2e2789a760062df8]

**Citations:** `by_paragraph-12c20f27e1251d18c440423d14c8faca25919a3d2b5e8c1a2e2789a760062df8`

**Cited evidence:**
- `by_paragraph-12c20f27e1251d18c440423d14c8faca25919a3d2b5e8c1a2e2789a760062df8`: `doc_0034` / page 1: By 2020, the Knowledge Graph had grown to 500 billion facts about 5 billion entities. But much of the “collective intelligence” that Google tapped into was content “misap

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: 500 billion facts about 5 billion entities.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

### d7-test-03

**Question:** According to the Epic Games trial preview, what commission range did Google charge app developers on sales processed through its first-party billing system?

**Expected:** 15% to 30%.

**Gold:** `doc_0043` / page 1 - charges app developers a 15% to 30% commission on the sales it processes.

#### dense_baseline

[Full trace](../../results/agent_test_final/dense_baseline/d7-test-03.json)

**Tool calls:** `search_dense` (Epic Games trial preview Google commission range app developers first-party) -> doc_0043:p1, doc_0043:p1

**Final answer:** According to the trial preview, Google requires apps to use its first-party billing system and charges app developers a 15% to 30% commission on the sales it processes [by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a].

**Citations:** `by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a`

**Cited evidence:**
- `by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a`: `doc_0043` / page 1: Google argues its commissions aren’t just tied to billing, but offers discount for third-party billing options Today, Google requires apps to use its own first-party bill

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: 15% to 30%.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

#### auto_english_v2

[Full trace](../../results/agent_test_final/auto_english_v2/d7-test-03.json)

**Tool calls:** `search_hybrid` (Epic Games trial preview Google commission range app developers first-party) -> doc_0043:p1, doc_0043:p1; `search_hybrid` (Google requires apps first-party billing system charges app developers 15% ) -> doc_0043:p1, doc_0043:p1

**Final answer:** Google charged app developers a 15% to 30% commission on sales processed through its first-party billing system [by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a].

**Citations:** `by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a`

**Cited evidence:**
- `by_paragraph-ad54cbc8ebbf6dd5bdae7bad3d6f63af951742add1409beb713ec22d9940104a`: `doc_0043` / page 1: Google argues its commissions aren’t just tied to billing, but offers discount for third-party billing options Today, Google requires apps to use its own first-party bill

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: 15% to 30%. Final answer is supported after two logged citation repairs.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

### d7-test-04

**Question:** In the Manchester United article, what planned infrastructure investment amount is mentioned in US dollars and pounds?

**Expected:** US$300 million, equivalent to 237 million pounds.

**Gold:** `doc_0090` / page 1 - invest $300m (£237m) into infrastructure

#### dense_baseline

[Full trace](../../results/agent_test_final/dense_baseline/d7-test-04.json)

**Tool calls:** `search_dense` (Manchester United planned infrastructure investment dollars pounds) -> doc_0090:p1, doc_0090:p1

**Final answer:** The article mentions a planned investment of $300m (£237m) into infrastructure [by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e].

**Citations:** `by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e`

**Cited evidence:**
- `by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e`: `doc_0090` / page 1: invest $300m (£237m) into infrastructure but this is small beer when considering the multibillion-pound facelift or new venue required. There is also the cramped Carringt

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: US$300 million, equivalent to 237 million pounds.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

#### auto_english_v2

[Full trace](../../results/agent_test_final/auto_english_v2/d7-test-04.json)

**Tool calls:** `search_hybrid` (Manchester United planned infrastructure investment US dollars pounds) -> doc_0090:p1, doc_0090:p1; `search_bm25` (Manchester United infrastructure investment £ $ billion) -> doc_0090:p1, doc_0090:p1

**Final answer:** The article mentions a planned infrastructure investment of $300m (£237m). [by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e]

**Citations:** `by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e`

**Cited evidence:**
- `by_paragraph-89c8adaaca7d8e7980b7474d26e84664026489a9f4baada229b9519688b8dc6e`: `doc_0090` / page 1: invest $300m (£237m) into infrastructure but this is small beer when considering the multibillion-pound facelift or new venue required. There is also the cramped Carringt

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: US$300 million, equivalent to 237 million pounds.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

### d7-test-05

**Question:** According to the Menendez article, what was the reported dollar value of gold bars found in the raid on his house?

**Expected:** $100,000.

**Gold:** `doc_0098` / page 1 - A raid of Menendez’s house turned up $100,000 in gold bars and bundles of cash stuffed into jacket pockets.

#### dense_baseline

[Full trace](../../results/agent_test_final/dense_baseline/d7-test-05.json)

**Tool calls:** `search_dense` (Menendez article dollar value gold bars found in raid on his house) -> doc_0098:p1, doc_0028:p1

**Final answer:** The article reported that the raid on Menendez’s house turned up **$100,000 in gold bars** [by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639].

**Citations:** `by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639`

**Cited evidence:**
- `by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639`: `doc_0098` / page 1: Menendez’s own adherence to the law happens to also be in question. In September, the Justice Department charged him and his wife Nadine with accepting bribes and alleged

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: $100,000.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

#### auto_english_v2

[Full trace](../../results/agent_test_final/auto_english_v2/d7-test-05.json)

**Tool calls:** `search_hybrid` (Menendez gold bars found in raid on his house dollar value) -> doc_0098:p1, doc_0028:p1; `search_bm25` (Menendez gold bars raid house value) -> doc_0098:p1, doc_0074:p1

**Final answer:** The article reports that the raid on Menendez's house turned up $100,000 in gold bars, along with bundles of cash stuffed into jacket pockets [by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639].

**Citations:** `by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639`

**Cited evidence:**
- `by_paragraph-4fb15dfec59b2bb48301a72153dc41f2afdb78853c226d21c6f7171a15397639`: `doc_0098` / page 1: Menendez’s own adherence to the law happens to also be in question. In September, the Justice Department charged him and his wife Nadine with accepting bribes and alleged

**AI-proposed:** G=2; C=2. Answer and cited evidence were inspected in the supplied test packet. Required fact: $100,000.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

### d7-test-u01

**Question:** What exact monthly subscription price in US dollars did Mozilla announce for Mozilla.social?

**Absence reason:** The article describes a private beta and moderation plans but gives no monthly subscription price. Absence of a price does not imply a zero-dollar price.

#### dense_baseline

[Full trace](../../results/agent_test_final/dense_baseline/d7-test-u01.json)

**Tool calls:** `search_dense` (Mozilla.social monthly subscription price US dollars) -> doc_0016:p1, doc_0027:p1

**Final answer:** The corpus does not provide enough evidence: the retrieved articles on Mozilla.social discuss Mozilla accounts and the instance's testing phase, but no monthly subscription price in US dollars is reported.

**Citations:** (none)

**Cited evidence:**
- No citations. Check abstention correctness.

**AI-proposed:** Abstention=correct. Correct abstention for this corpus benchmark. The article describes a private beta and moderation plans but gives no monthly subscription price. Absence of a price does not imply a zero-dollar price.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

#### auto_english_v2

[Full trace](../../results/agent_test_final/auto_english_v2/d7-test-u01.json)

**Tool calls:** `search_hybrid` (Mozilla.social monthly subscription price US dollars announced) -> doc_0027:p1, doc_0027:p1; `search_bm25` (Mozilla.social subscription price per month) -> doc_0027:p1, doc_0027:p1; `search_dense` (Mozilla.social paid subscription cost per month dollars) -> doc_0016:p1, doc_0027:p1

**Final answer:** The corpus does not provide enough evidence to confirm the exact monthly subscription price Mozilla announced for Mozilla.social.

**Citations:** (none)

**Cited evidence:**
- No citations. Check abstention correctness.

**AI-proposed:** Abstention=correct. Correct abstention for this corpus benchmark. The article describes a private beta and moderation plans but gives no monthly subscription price. Absence of a price does not imply a zero-dollar price.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

### d7-test-u02

**Question:** What exact dollar amount in damages did the court ultimately award Helena World Chronicle in its lawsuit against Google?

**Absence reason:** The snapshot describes a newly filed lawsuit and requested relief, not a damages award. Google's Canadian media agreement is a different matter.

#### dense_baseline

[Full trace](../../results/agent_test_final/dense_baseline/d7-test-u02.json)

**Tool calls:** `search_dense` (Helena World Chronicle lawsuit against Google damages awarded) -> doc_0034:p1, doc_0034:p1

**Final answer:** The corpus does not provide enough evidence to answer this. The only relevant material describes the December 2023 class action filed by Helena World Chronicle against Google and Alphabet, but it reports no damages award or outcome, so no dollar amount can be given.

**Citations:** (none)

**Cited evidence:**
- No citations. Check abstention correctness.

**AI-proposed:** Abstention=correct. Correct abstention for this corpus benchmark. The snapshot describes a newly filed lawsuit and requested relief, not a damages award. Google's Canadian media agreement is a different matter.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____

#### auto_english_v2

[Full trace](../../results/agent_test_final/auto_english_v2/d7-test-u02.json)

**Tool calls:** `search_hybrid` (Helena World Chronicle lawsuit against Google damages awarded) -> doc_0034:p1, doc_0034:p1; `search_bm25` (Helena World Chronicle Google) -> doc_0034:p1, doc_0034:p1; `search_dense` (Helena World Chronicle verdict damages awarded amount outcome ruling) -> doc_0034:p1, doc_0003:p1

**Final answer:** The corpus does not provide enough evidence to state a damages award in this case.

**Citations:** (none)

**Cited evidence:**
- No citations. Check abstention correctness.

**AI-proposed:** Abstention=correct. Correct abstention for this corpus benchmark. The snapshot describes a newly filed lawsuit and requested relief, not a damages award. Google's Canadian media agreement is a different matter.

- [ ] Checked answer against expected/absence.
- [ ] Checked semantic support for every claim.
- [ ] Checked citation IDs against active context.
- [ ] Confirmed or corrected AI-proposed grade.
- Reviewer: _____; Date: _____; Conclusion: _____


---

### Assistant cross-check summary

Status: AI-assisted cross-check completed.
Human confirmation remains pending.

| Query | Dense baseline | Agent v2 | Evidence |
|---|---|---|---|
| d7-test-01 | Correct | Correct | 9 ZB; baseline extra 2023 comparison supported jointly |
| d7-test-02 | False abstention | Correct | 500 billion facts; 5 billion entities |
| d7-test-03 | Correct | Correct | 15%-30% commission |
| d7-test-04 | Correct | Correct | $300m and GBP 237m |
| d7-test-05 | Correct | Correct | $100,000 in gold bars |
| d7-test-u01 | Appropriate abstention | Appropriate abstention | Monthly price absent in related evidence |
| d7-test-u02 | Appropriate abstention | Appropriate abstention | No damages award in the article snapshot |

Proposed scores:
- Dense baseline: groundedness 8/10.
- Agent v2: groundedness 10/10.
- Both profiles: 2/2 proposed correct abstentions.
- No original scores or traces were modified.

Outstanding verification:
- Confirm unanswerable cases against the full corpus.
- Verify all cited chunks in the original traces.
- Record actual reviewer and date before claiming human confirmation.

This section is an independent AI-assisted review,
not a human-confirmed evaluation.

</details>

- Kết quả trước/sau, ví dụ lỗi, đánh đổi và giới hạn:

V2 giảm một false abstention trên 5 câu test có đáp án, đổi lấy gần gấp đôi median latency và nhiều token/model calls hơn baseline. Perfect score trong mẫu nhỏ không chứng minh khả năng tổng quát. Test được người soạn/AI biết đáp án khi tạo benchmark, không phải đánh giá mù bởi bên độc lập.



Nhãn semantic và absence mới là AI-proposed; người học cần đối chiếu trước khi tự xác nhận. Fixture/mocked unit tests chỉ kiểm tra hành vi code, không thay thế benchmark agent thật. Bộ test code đã chạy 21 tests, OK.



Chưa đánh giá bảng, ảnh, biểu đồ hoặc tài liệu 100 trang, chưa có bonus. Chunk 500 ký tự có thể cắt câu; exact-quote metric không bao quát mọi paraphrase/multi-hop. Hash corpus xác nhận ID/text/source/position, không đóng băng mọi vector/provider snapshot. Temperature=0 không bảo đảm output giống tuyệt đối khi model alias, API hoặc môi trường thay đổi. Retrieved content được coi là dữ liệu không tin cậy, nhưng chưa benchmark prompt injection.

<!-- day7-implementation-guide -->
<a id="submission-run-guide"></a>

<details>
<summary>Hướng dẫn chạy bài làm</summary>

### Day 7 — Agentic Retrieval & Context Engineering

Trần Đức Trung · 2A202603938 · L3B.

Dense/BM25/hybrid trên cùng index Day 6; agent thật có tool calling, citation và abstention.

[Báo cáo cá nhân](../../report/individual/2A202603938_TranDucTrung.md) · [Tổng hợp kết quả](../../results/submission_summary.json) · [Cấu hình đã chốt](../../configs/final_selection.json) · [Đề bài gốc](https://github.com/VinUni-AI20k/K5-L3-Day07-Retrieval-Context-Engineering).

### Kết quả đã lưu

Test: 5 câu có đáp án + 2 thiếu evidence. Baseline grounded mean 1.6/2, context 4/5, abstention đúng 2/2; v2 mean 2/2, context 5/5, abstention đúng 2/2. Median lần lượt 5.03s và 9.54s. Nhãn là ai_proposed, chưa được xác nhận độc lập bởi người chấm. Chi tiết query gốc, query viết lại, lỗi và chi phí raw trong báo cáo.

### Cài đặt Windows PowerShell

Môi trường đã chạy: Python 3.13.3, Docker Compose và Git. Chạy tại thư mục gốc Day 7:

```powershell
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env

```

Điền API key cá nhân trong .env. AGENT_API_KEY/AGENT_BASE_URL trống thì dùng OPENAI_API_KEY/OPENAI_BASE_URL. DATABASE_URL mẫu dành PostgreSQL local. Không commit .env.

### Dữ liệu và tái tạo index

Nguồn Day 6: [7aa3adc7a0bf](https://github.com/kientrungtd135/K5-L3B-DAY06-TranDucTrung-2A202603938-DataIngestion/tree/7aa3adc7a0bf794daa654156b06bf9743403b763); manifest tại starter/data/manifest.json. Có 30 bài Markdown, 701 chunk B, embedding text-embedding-3-small 1536 chiều. Dataset MultiHopRAG khai báo ODC-BY; quyền riêng từng bài báo chưa được xác nhận. Giữ URL/attribution. page=1 là article unit.

Nếu đã có database Day 6, khởi động và kiểm tra từ Day 7:

```powershell
docker compose -p day6_student_starter -f "..\K5-L3B-DAY06-TranDucTrung-2A202603938-DataIngestion\starter\docker-compose.yml" up -d --wait
& .\.venv\Scripts\python.exe -X utf8 -m src.day6_bridge
```

Các lệnh kiểm tra không gọi embedding API. Cần thấy B: 701 chunks, 30 documents, 1536 dimensions; review_dev kiểm tra corpus hash.

Chỉ khi database mới chưa có index: tái tạo bằng DEV Day 6 tại commit được pin. Bước này gọi API và phát sinh phí; không cần chạy TEST Day 6.

```powershell
$Day7Root = (Get-Location).Path
New-Item -ItemType Directory -Force .\deps | Out-Null
git clone https://github.com/kientrungtd135/K5-L3B-DAY06-TranDucTrung-2A202603938-DataIngestion.git .\deps\day6
git -C .\deps\day6 checkout 7aa3adc7a0bf794daa654156b06bf9743403b763
$Day6Env = Join-Path $Day7Root "deps\day6\starter\.env"
$EnvText = Get-Content -LiteralPath .\.env -Raw -Encoding UTF8
[System.IO.File]::WriteAllText($Day6Env, $EnvText, [System.Text.UTF8Encoding]::new($false))
Push-Location .\deps\day6\starter
try {
    docker compose -p day6_student_starter up -d --wait
    & "$Day7Root\.venv\Scripts\python.exe" -X utf8 -m src.run
} finally { Pop-Location }
& .\.venv\Scripts\python.exe -X utf8 -m src.day6_bridge
```

DEV Day 6 tạo A/B/C; Day 7 chỉ đọc B. deps/ được ignore. Model/API thay đổi có thể làm vector hoặc ranking khác. Không xóa Docker volume chứa index để dọn repo.

### Kiểm tra và tổng hợp, không gọi API

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -X utf8 -m src.summarize_results
```

21 unit tests đã pass, gồm sáu guard tests v2. Unit tests không thay thế benchmark agent thật. Tổng hợp kiểm tra hash pipeline/review; không tự chấm semantic hoặc đổi AI-proposed thành human-confirmed.

### Chạy agent và tái lập thí nghiệm

Các lệnh sau có gọi API, phát sinh phí. Dùng output mới để giữ trace cũ:

```powershell
$RunTag = Get-Date -Format "yyyyMMdd_HHmmss"
& .\.venv\Scripts\python.exe -X utf8 -m src.agent_v2 --method auto --query-id d7-dev-q09 --output ".\results\reproduction\demo_$RunTag.json"
& .\.venv\Scripts\python.exe -X utf8 -m src.evaluate_agent --run-name "reproduce_v1_$RunTag"
& .\.venv\Scripts\python.exe -X utf8 -m src.evaluate_agent_v2 --run-name "reproduce_v2_$RunTag"
```

Tạo benchmark trên workspace mới chưa có benchmark/*.json: `python -X utf8 -m src.prepare_benchmark --day6-root PATH_TO_DAY6`, dùng nguồn Day 6 được pin.

Ranking query gốc dev: `python -X utf8 -m src.evaluate_retrieval`; chạy khi chưa có output hoặc dùng --resume để giữ thành công và retry lỗi.

Luồng gốc: tạo benchmark -> retrieval DEV -> agent v1 DEV -> đọc/chấm -> v2 DEV -> đọc/chấm -> freeze và TEST qua src.final_test -> đọc/chấm TEST -> tổng hợp.

`python -X utf8 -m src.final_test --resume` chỉ dành tiếp tục lỗi hệ thống với pipeline đã đóng băng, giữ câu thành công. Bài hiện đã chạy xong TEST; không chỉnh theo test hoặc xóa trace để chạy lại lấy kết quả tốt hơn. Muốn chọn cấu hình khác cần test độc lập mới.

### Các file chính

- src/: bridge Day 6, retrieval, agent v1/v2, runner, review, tổng hợp và tạo báo cáo.
- benchmark/: 24 câu, evidence, absence audit, fingerprint.
- configs/final_selection.json: cấu hình và hash chốt trước test.
- results/retrieval_dev/: query gốc dev.
- results/agent_test_final/raw_retrieval/: query gốc test.
- results/agent_dev_v1/, agent_dev_v2/, agent_test_final/: trace, plan, automatic summary và review.
- starter/*.py, data/example_*.json, tests/: dependency và fixture kiểm thử.

Chỉ làm phần cơ bản, không có bonus. Provider cost raw chưa xác nhận đơn vị tiền tệ. Tổng hợp không bao gồm smoke checks và tạo index Day 6. Nộp link repo cá nhân có quyền xem; không push vào upstream đề bài.

</details>

## Thử thách nâng cao (nếu thực hiện)

- Tài liệu, nguồn, quyền sử dụng, số trang và phiên bản: không thực hiện trong bài nộp này.
- Cách xử lý text, bảng, ảnh, biểu đồ; phạm vi index và phần chưa xử lý: không áp dụng.
- Cách chia benchmark, schema evidence, model và cấu hình đã chốt trên dev: không áp dụng cho bonus.

| Nhóm test | Đạt / tổng | Tỷ lệ | Lỗi / nhận xét |
| --- | --- | --- | --- |
| Bảng | N/A | N/A | Không thực hiện benchmark nâng cao. |
| Ảnh, sơ đồ | N/A | N/A | Không thực hiện benchmark nâng cao. |
| Biểu đồ | N/A | N/A | Không thực hiện benchmark nâng cao. |
| Multi-hop | N/A | N/A | Không thực hiện benchmark nâng cao. |
| Text | N/A | N/A | Không thực hiện benchmark nâng cao. |
| Thiếu bằng chứng | N/A | N/A | Không thực hiện benchmark nâng cao. |
| **Toàn bộ** | N/A | N/A | Không thực hiện benchmark nâng cao. |

- Trace, nhãn và evidence từng câu; thời gian, chi phí, lỗi hệ thống: không áp dụng cho bonus.
- Giới hạn, cách tái lập và đường dẫn benchmark: phần cơ bản được mô tả ở các mục trên; không dùng kết quả phần cơ bản để tính điểm bonus.
