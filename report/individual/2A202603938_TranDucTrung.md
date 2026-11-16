# Báo cáo cá nhân Day 7

## 1. Dữ liệu và benchmark

Kế thừa index B Day 6: 30 bài Markdown, gồm 15 business và 15 technology; chunk theo đoạn với max_size=500 ký tự, tổng cộng 701 chunk. page=1 là đơn vị bài viết, không phải trang PDF.

Vector store: PostgreSQL 16 + pgvector 0.8.7, bảng public.day6_chunks, strategy B, tìm kiếm cosine exact. Embedding: text-embedding-3-small, 1536 chiều. Agent thật: deepseek-v4.1-flash qua API tương thích OpenAI tại https://api.xah.io/v1. Model ID là alias provider, không bảo đảm snapshot bất biến.

Môi trường đã chạy: Windows, Python 3.13.3; openai 2.54.0, psycopg 3.3.8, python-dotenv 1.2.4, rank-bm25 0.2.2, numpy 2.5.5, pypdf 6.21.4. Các dependency được pin trong requirements.txt.

Benchmark gồm 24 câu: dev có 15 câu có đáp án + 2 câu thiếu evidence; test có 5 câu có đáp án mới + 2 câu thiếu evidence. Dev tái sử dụng câu hỏi dev Day 6. Năm câu test có đáp án dùng nguồn khác các nguồn câu hỏi Day 6. Cả 20 gold quote đều nằm trọn trong chunk B đúng source/page. Agent chỉ nhận câu hỏi và filter được cung cấp, không nhận expected answer, gold hoặc absence reason.

Bốn câu thiếu evidence hỏi về tỷ trọng doanh số Ripple Rug năm 2022, lợi nhuận sau thuế Betashares FY2023, giá thuê bao Mozilla.social và phán quyết bồi thường Helena World Chronicle. Lý do và dấu vết tìm kiếm nằm trong benchmark/absence_audit.json. AI đối chiếu nguồn liên quan và tìm trong corpus; không kết luận thiếu dữ liệu chỉ từ top-k. Nhãn absence chưa có xác nhận độc lập.

Nguồn dữ liệu là subset MultiHopRAG, dataset khai báo ODC-BY. URL/attribution được giữ trong manifest và trace. License dataset không xác nhận riêng quyền phân phối từng bài báo. Day 7 cung cấp nguồn Day 6 và cách tái tạo; trace vẫn chứa các đoạn nguồn đã dùng.

Nguồn Day 6: Manifest tại starter/data/manifest.json trong repo.

## 2. Phương pháp và cấu hình

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

## 3. Retrieval với query gốc

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

## 4. Agent: context, câu trả lời và citation

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

## 5. Lỗi dev, thay đổi và lựa chọn trước test

1. **d7-dev-q09 — từ chối nhầm.** Query gốc dense có evidence newsletter tại rank 2, nhưng query baseline do model viết lại lấy các đoạn podcast ở doc_0012, thiếu lịch newsletter ở doc_0010. Một search không khôi phục được evidence: grounded/context 0. Auto bổ sung search; v2 trả lời đúng Thursday 12 p.m. PT, grounded/context 2. Query gốc tốt không bảo đảm query viết lại tốt.

2. **d7-dev-q13 — thêm chi tiết thiếu evidence.** Dense/BM25/hybrid trả lời đúng phần API nhưng hoàn tất thêm ý wireless-carrier từ câu bị cắt mà chưa có continuation trong context. Chấm bảo thủ grounded 1, citation chưa hỗ trợ toàn bộ câu. Auto v1 có các đoạn bổ sung nên được 2; v2 chỉ trả lời phần hỏi và được 2. Exact gold match không có nghĩa toàn bộ câu đều được hỗ trợ.

3. **Ngôn ngữ và citation khi abstain.** V1 có 2/4/2 lỗi ngôn ngữ ở dense/BM25/hybrid. Hybrid dev-u02 có inline citation nhưng list rỗng: citation hỗ trợ nguồn vẫn tính vào denominator, đồng thời báo một lỗi format. V2 thêm guard/prompt và sáu regression tests. Hai repair v2 dev là sửa citation ở q03/q07, không phải sửa ngôn ngữ.

BM25 và hybrid là hai cấu hình thử cải thiện, đồng thời là hai phương pháp retrieval mới. Auto và v2 là các thử nghiệm tiếp theo. Tiêu chí ban đầu: mean grounded cao nhất, rồi context, citation, latency. Trong dev, chính sách được điều chỉnh ưu tiên implementation có guard ngôn ngữ/citation abstention; thay đổi và lý do được ghi trong final_selection trước test.

Auto v1 cũng đạt 30/30 điểm dev và nhanh hơn v2. Nếu chỉ dùng tiêu chí điểm và latency ban đầu, Auto v1 sẽ được ưu tiên. V2 được chọn vì guard ở mức code cùng prompt hạn chế phát biểu thêm, chấp nhận latency cao hơn; không tuyên bố v2 tăng factual accuracy dev so với Auto v1. Guard v1 vẫn có lỗ hổng dù các output Auto v1 quan sát được đều đạt.

Test chỉ chạy sau freeze; không sửa prompt/parameter theo lỗi test hoặc chạy lại câu thành công để chọn kết quả đẹp. Test-02 baseline từ chối nhầm vì query viết lại không tìm được counts, còn v2 tìm đủ evidence. Test-03 v2 cần 6 model calls, 2 searches và 2 citation repairs; giữ nguyên trong trace.

Dense query gốc test đạt 5/5, BM25/hybrid đạt 4/5; không kết luận hybrid luôn tốt hơn dense.

## 6. Lượt gọi, token và chi phí

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

## 7. Đối chiếu từng câu test

Bảng lấy trực tiếp từ trace và reviews gốc. Các nhãn vẫn là **AI-proposed**, chưa được human-confirmed. Xem [phiếu kiểm chứng](manual_review.md).

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

## 8. Giới hạn và kết luận

V2 giảm một false abstention trên 5 câu test có đáp án, đổi lấy gần gấp đôi median latency và nhiều token/model calls hơn baseline. Perfect score trong mẫu nhỏ không chứng minh khả năng tổng quát. Test được người soạn/AI biết đáp án khi tạo benchmark, không phải đánh giá mù bởi bên độc lập.

Nhãn semantic và absence mới là AI-proposed; người học cần đối chiếu trước khi tự xác nhận. Fixture/mocked unit tests chỉ kiểm tra hành vi code, không thay thế benchmark agent thật. Bộ test code đã chạy 21 tests, OK.

Chưa đánh giá bảng, ảnh, biểu đồ hoặc tài liệu 100 trang, chưa có bonus. Chunk 500 ký tự có thể cắt câu; exact-quote metric không bao quát mọi paraphrase/multi-hop. Hash corpus xác nhận ID/text/source/position, không đóng băng mọi vector/provider snapshot. Temperature=0 không bảo đảm output giống tuyệt đối khi model alias, API hoặc môi trường thay đổi. Retrieved content được coi là dữ liệu không tin cậy, nhưng chưa benchmark prompt injection.
